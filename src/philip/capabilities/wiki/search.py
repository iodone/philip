"""BM25 + ripgrep search engine with CJK tokenizer and RRF fusion."""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path

from philip.capabilities.wiki.wiki import WikiPage

# ---------------------------------------------------------------------------
# CJK tokenizer
# ---------------------------------------------------------------------------

# Unicode ranges for CJK characters (unified + extension + compat + kana + hangul)
_CJK_RE = re.compile(r"[一-鿿㐀-䶿豈-﫿" r"　-〿぀-ゟ゠-ヿ가-힯]")


def tokenize(text: str) -> list[str]:
    """Tokenize *text* into words (split on whitespace) and CJK unigrams + bigrams."""
    tokens: list[str] = []
    normalized = text.lower()
    i = 0
    non_cjk_buf = ""

    while i < len(normalized):
        ch = normalized[i]
        if _CJK_RE.match(ch):
            # Flush non-CJK buffer
            if non_cjk_buf:
                tokens.extend(t for t in non_cjk_buf.split() if t)
                non_cjk_buf = ""
            # Emit unigram
            tokens.append(ch)
            # Emit bigram with next CJK char
            if i + 1 < len(normalized) and _CJK_RE.match(normalized[i + 1]):
                tokens.append(ch + normalized[i + 1])
            i += 1
        else:
            non_cjk_buf += ch
            i += 1

    if non_cjk_buf:
        tokens.extend(t for t in non_cjk_buf.split() if t)
    return tokens


# ---------------------------------------------------------------------------
# BM25 index
# ---------------------------------------------------------------------------

_K1 = 1.2
_B = 0.75


@dataclass
class _BM25Index:
    df: dict[str, int]  # document frequency per token
    tf: list[dict[str, int]]  # term frequency per document
    doc_lengths: list[int]  # token count per document
    avg_dl: float  # average document length
    n: int  # total documents


def _build_index(pages: list[WikiPage]) -> _BM25Index:
    df: dict[str, int] = {}
    tf_list: list[dict[str, int]] = []
    doc_lengths: list[int] = []

    for page in pages:
        text = f"{page.title} {page.description or ''} {page.content}"
        tokens = tokenize(text)
        doc_lengths.append(len(tokens))

        term_freq: dict[str, int] = {}
        seen: set[str] = set()
        for tok in tokens:
            term_freq[tok] = term_freq.get(tok, 0) + 1
            seen.add(tok)
        tf_list.append(term_freq)

        for term in seen:
            df[term] = df.get(term, 0) + 1

    total_len = sum(doc_lengths)
    n = len(pages)
    avg_dl = total_len / n if n > 0 else 0.0

    return _BM25Index(df=df, tf=tf_list, doc_lengths=doc_lengths, avg_dl=avg_dl, n=n)


def _score_bm25(index: _BM25Index, query_tokens: list[str], doc_idx: int) -> float:
    doc_tf = index.tf[doc_idx]
    dl = index.doc_lengths[doc_idx]
    score = 0.0

    for token in query_tokens:
        doc_freq = index.df.get(token, 0)
        if doc_freq == 0:
            continue
        idf = math.log((index.n - doc_freq + 0.5) / (doc_freq + 0.5) + 1)
        tf = doc_tf.get(token, 0)
        tf_norm = (tf * (_K1 + 1)) / (tf + _K1 * (1 - _B + _B * dl / index.avg_dl))
        score += idf * tf_norm

    return score


# ---------------------------------------------------------------------------
# Search API
# ---------------------------------------------------------------------------


@dataclass
class SearchResult:
    page: WikiPage
    score: float


def bm25_search(
    pages: list[WikiPage],
    query: str,
    limit: int = 10,
) -> list[SearchResult]:
    """Run BM25 search across *pages* for *query*."""
    if not pages:
        return []

    index = _build_index(pages)
    query_tokens = tokenize(query)

    results: list[SearchResult] = []
    for i, page in enumerate(pages):
        score = _score_bm25(index, query_tokens, i)
        if score > 0:
            results.append(SearchResult(page=page, score=score))

    results.sort(key=lambda r: r.score, reverse=True)
    return results[:limit]


# ---------------------------------------------------------------------------
# Grep search (ripgrep)
# ---------------------------------------------------------------------------


def grep_search(
    wiki_dir: str,
    query: str,
    limit: int = 10,
) -> list[SearchResult]:
    """Run ripgrep across wiki markdown files and return matches.

    Uses ripgrepy SDK. Returns one result per matching file with
    score = match count (ranked by relevance).
    """
    try:
        from ripgrepy import Ripgrepy
    except ImportError:
        return []

    wiki_path = Path(wiki_dir)
    if not wiki_path.exists():
        return []

    rg = Ripgrepy(query, str(wiki_path))
    rg = rg.type_("md").json()

    try:
        raw = rg.run().as_string
    except Exception:
        return []

    # Parse JSON lines output, group by file
    matches: dict[str, int] = {}
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if entry.get("type") != "match":
            continue
        path = entry.get("data", {}).get("path", {}).get("text", "")
        if path:
            matches[path] = matches.get(path, 0) + 1

    if not matches:
        return []

    # Convert file paths to slugs and build results
    results: list[SearchResult] = []
    for file_path, count in sorted(matches.items(), key=lambda x: x[1], reverse=True):
        p = Path(file_path)
        # Derive slug: strip wiki_dir prefix and .md extension
        try:
            rel = p.relative_to(wiki_path)
        except ValueError:
            continue
        slug = str(rel.with_suffix("")).replace("/", ".")

        results.append(SearchResult(
            page=WikiPage(path=p, relative_path=str(rel), slug=slug, title=slug),
            score=float(count),
        ))

    return results[:limit]


# ---------------------------------------------------------------------------
# Reciprocal Rank Fusion
# ---------------------------------------------------------------------------


def rrf_merge(
    bm25_results: list[dict[str, float]],
    vector_results: list[dict[str, float]],
    limit: int,
    k: int = 60,
) -> list[dict[str, float]]:
    """Merge two ranked result lists using Reciprocal Rank Fusion (k=60)."""
    scores: dict[str, float] = {}

    for rank, r in enumerate(bm25_results):
        slug = r["slug"]
        scores[slug] = scores.get(slug, 0.0) + 1.0 / (k + rank + 1)

    for rank, r in enumerate(vector_results):
        slug = r["slug"]
        scores[slug] = scores.get(slug, 0.0) + 1.0 / (k + rank + 1)

    merged = [{"slug": s, "score": sc} for s, sc in scores.items()]
    merged.sort(key=lambda r: r["score"], reverse=True)
    return merged[:limit]
