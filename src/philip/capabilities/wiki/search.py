"""Block-level BM25 + ripgrep search with tiered ranking.

Design: docs/llm-wiki-search-architecture.md
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class Block:
    """A chunk of markdown split by header boundaries."""

    file_path: str
    slug: str
    header: str  # e.g. "### 慢查询排查"
    content: str  # full block text including header
    line_start: int
    line_end: int


@dataclass
class SearchResult:
    """A search hit with ranking metadata."""

    block: Block
    score: float
    match_type: str  # "exact" | "semantic"


# ---------------------------------------------------------------------------
# Tokenizer (jieba)
# ---------------------------------------------------------------------------


def tokenize(text: str) -> list[str]:
    """Tokenize text using jieba. Filters out whitespace-only tokens."""
    import jieba

    return [t for t in jieba.lcut(text.lower()) if t.strip()]


# ---------------------------------------------------------------------------
# Markdown block parser
# ---------------------------------------------------------------------------

_HEADER_RE = re.compile(r"^(#{1,6})\s+")


def parse_blocks(file_path: str, content: str, wiki_dir: str) -> list[Block]:
    """Split markdown content into blocks by headers.

    Each block carries its header, content, and line range.
    Blocks without a header get header="".
    """
    p = Path(file_path)
    try:
        rel = p.relative_to(wiki_dir)
    except ValueError:
        rel = p
    slug = str(rel.with_suffix("")).replace("/", ".")

    lines = content.split("\n")
    blocks: list[Block] = []
    current_header = ""
    current_lines: list[str] = []
    line_start = 1

    for i, line in enumerate(lines, 1):
        if _HEADER_RE.match(line):
            # Flush previous block
            if current_lines:
                blocks.append(Block(
                    file_path=file_path,
                    slug=slug,
                    header=current_header,
                    content="\n".join(current_lines),
                    line_start=line_start,
                    line_end=i - 1,
                ))
            current_header = line.strip()
            current_lines = [line]
            line_start = i
        else:
            current_lines.append(line)

    # Final block
    if current_lines:
        blocks.append(Block(
            file_path=file_path,
            slug=slug,
            header=current_header,
            content="\n".join(current_lines),
            line_start=line_start,
            line_end=len(lines),
        ))

    return blocks


# ---------------------------------------------------------------------------
# BM25 index (block-level)
# ---------------------------------------------------------------------------

_K1 = 1.2
_B = 0.75


@dataclass
class _BM25Index:
    df: dict[str, int]
    tf: list[dict[str, int]]
    doc_lengths: list[int]
    avg_dl: float
    n: int


def _build_block_index(blocks: list[Block]) -> _BM25Index:
    df: dict[str, int] = {}
    tf_list: list[dict[str, int]] = []
    doc_lengths: list[int] = []

    for block in blocks:
        tokens = tokenize(block.content)
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
    n = len(blocks)
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
# BM25 search (block-level)
# ---------------------------------------------------------------------------


def bm25_search(
    blocks: list[Block],
    query_tokens: list[str],
    limit: int = 20,
) -> list[SearchResult]:
    """Run BM25 over blocks and return ranked results."""
    if not blocks or not query_tokens:
        return []

    index = _build_block_index(blocks)

    results: list[SearchResult] = []
    for i, block in enumerate(blocks):
        score = _score_bm25(index, query_tokens, i)
        if score > 0:
            results.append(SearchResult(block=block, score=score, match_type="semantic"))

    results.sort(key=lambda r: r.score, reverse=True)
    return results[:limit]


# ---------------------------------------------------------------------------
# Grep search (ripgrep) — block-level hit mapping
# ---------------------------------------------------------------------------


def grep_search(
    wiki_dir: str,
    pattern: str,
    limit: int = 50,
) -> dict[str, list[int]]:
    """Run ripgrep and return {file_path: [line_numbers]}."""
    try:
        from ripgrepy import Ripgrepy
    except ImportError:
        return {}

    wiki_path = Path(wiki_dir)
    if not wiki_path.exists():
        return {}

    rg = Ripgrepy(pattern, str(wiki_path))
    rg = rg.type_("md").json()

    try:
        raw = rg.run().as_string
    except Exception:
        return {}

    hits: dict[str, list[int]] = {}
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
        line_no = entry.get("data", {}).get("line_number", 0)
        if path and line_no:
            hits.setdefault(path, []).append(line_no)

    return hits


def _line_in_block(block: Block, line_no: int) -> bool:
    """Check if a line number falls within a block's range."""
    return block.line_start <= line_no <= block.line_end


# ---------------------------------------------------------------------------
# Tiered ranking
# ---------------------------------------------------------------------------


def tiered_rank(
    blocks: list[Block],
    exact_terms: list[str],
    fuzzy_terms: list[str],
    wiki_dir: str,
    limit: int = 10,
) -> list[SearchResult]:
    """Dual-path retrieval with tiered ranking.

    Tier 1 (VIP): grep hit block that also contains exact_terms → force top
    Tier 2: BM25 high score (fuzzy_terms semantic match)
    """
    all_terms = exact_terms + fuzzy_terms
    if not all_terms:
        return []

    # --- BM25 path ---
    bm25_results = bm25_search(blocks, tokenize(" ".join(all_terms)), limit * 3)

    # --- Grep path (exact_terms only) ---
    grep_hits: dict[str, list[int]] = {}
    if exact_terms:
        pattern = "|".join(re.escape(t) for t in exact_terms)
        grep_hits = grep_search(wiki_dir, pattern, limit * 3)

    # --- Map grep hits to blocks ---
    grep_block_keys: set[str] = set()  # "file_path:line_start"
    for file_path, line_nos in grep_hits.items():
        for block in blocks:
            if block.file_path == file_path:
                for ln in line_nos:
                    if _line_in_block(block, ln):
                        grep_block_keys.add(f"{block.file_path}:{block.line_start}")
                        break

    # --- Tier assignment ---
    exact_term_set = {t.lower() for t in exact_terms}

    tier1: list[SearchResult] = []
    tier2: list[SearchResult] = []
    seen_keys: set[str] = set()

    for r in bm25_results:
        key = f"{r.block.file_path}:{r.block.line_start}"
        if key in seen_keys:
            continue
        seen_keys.add(key)

        block_text_lower = r.block.content.lower()
        has_exact = any(t in block_text_lower for t in exact_term_set)
        grep_hit = key in grep_block_keys

        if grep_hit and has_exact:
            tier1.append(SearchResult(block=r.block, score=r.score + 100.0, match_type="exact"))
        else:
            tier2.append(r)

    # Also add grep-only hits not in BM25 results
    for file_path, line_nos in grep_hits.items():
        for block in blocks:
            if block.file_path != file_path:
                continue
            for ln in line_nos:
                if _line_in_block(block, ln):
                    key = f"{block.file_path}:{block.line_start}"
                    if key not in seen_keys:
                        seen_keys.add(key)
                        block_text_lower = block.content.lower()
                        has_exact = any(t in block_text_lower for t in exact_term_set)
                        if has_exact:
                            tier1.append(SearchResult(block=block, score=100.0, match_type="exact"))
                    break

    # Sort each tier
    tier1.sort(key=lambda r: r.score, reverse=True)
    tier2.sort(key=lambda r: r.score, reverse=True)

    return (tier1 + tier2)[:limit]
