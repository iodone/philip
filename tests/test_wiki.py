"""Tests for philip.wiki core modules — config, wiki, search, graph, sync, skills."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    """Create a minimal wiki vault structure for testing."""
    wiki_pages = tmp_path / "wiki" / "pages"
    wiki_pages.mkdir(parents=True)
    contexts = tmp_path / "contexts"
    contexts.mkdir()
    llm_wiki_dir = tmp_path / ".llm-wiki"
    llm_wiki_dir.mkdir()

    # Config
    (llm_wiki_dir / "config.toml").write_text(
        '[vault]\nname = "Test Wiki"\nlanguage = "en"\n',
        encoding="utf-8",
    )

    # Some wiki pages
    (wiki_pages / "raft-consensus.md").write_text(
        """---
title: Raft Consensus
description: A consensus algorithm for distributed systems
tags: [concept, distributed]
aliases: [Raft]
---

Raft is a consensus algorithm. It uses [[leader-election]] and [[log-replication]].

## Related

- [[paxos]] — alternative consensus algorithm
""",
        encoding="utf-8",
    )

    (wiki_pages / "leader-election.md").write_text(
        """---
title: Leader Election
description: How Raft elects leaders
tags: [concept, distributed]
---

Leader election in Raft uses randomized timeouts. See [[raft-consensus]].
""",
        encoding="utf-8",
    )

    (wiki_pages / "log-replication.md").write_text(
        """---
title: Log Replication
description: How Raft replicates logs
tags: [concept, distributed]
---

Log replication ensures consistency. Related to [[raft-consensus]].
""",
        encoding="utf-8",
    )

    (wiki_pages / "apache-kafka.md").write_text(
        """---
title: Apache Kafka
description: Distributed event streaming platform
tags: [system, streaming]
aliases: [Kafka]
---

Kafka uses a variant of [[raft-consensus]] for metadata management.
""",
        encoding="utf-8",
    )

    # Purpose and schema
    (tmp_path / "wiki" / "wiki-purpose.md").write_text("# Purpose\nTest wiki.\n", encoding="utf-8")
    (tmp_path / "wiki" / "wiki-schema.md").write_text("# Schema\nStandard.\n", encoding="utf-8")
    (tmp_path / "wiki" / "wiki-log.md").write_text("# Log\n## [2026-01-01] init\nCreated.\n", encoding="utf-8")

    return tmp_path


# ---------------------------------------------------------------------------
# Config tests
# ---------------------------------------------------------------------------


class TestConfig:
    def test_find_vault_root(self, vault: Path) -> None:
        from philip.wiki.config import find_vault_root

        root = find_vault_root(vault / "wiki" / "pages")
        assert root == vault

    def test_find_vault_root_returns_none_outside(self, tmp_path: Path) -> None:
        from philip.wiki.config import find_vault_root

        assert find_vault_root(tmp_path) is None

    def test_require_vault_root_raises_outside(self, tmp_path: Path) -> None:
        from philip.wiki.config import require_vault_root

        with pytest.raises(SystemExit):
            require_vault_root(tmp_path)

    def test_load_config(self, vault: Path) -> None:
        from philip.wiki.config import load_config

        config = load_config(vault)
        assert config.vault.name == "Test Wiki"
        assert config.vault.language == "en"

    def test_load_config_defaults_when_missing(self, tmp_path: Path) -> None:
        from philip.wiki.config import load_config

        config = load_config(tmp_path)
        assert config.vault.name == "My Wiki"
        assert config.vault.language == "en"

    def test_vault_paths(self, vault: Path) -> None:
        from philip.wiki.config import load_config, vault_paths

        config = load_config(vault)
        paths = vault_paths(vault, config)

        assert paths.wiki == vault / "wiki" / "pages"
        assert paths.wiki_root == vault / "wiki"
        assert paths.contexts == vault / "contexts"
        assert paths.purpose == vault / "wiki" / "wiki-purpose.md"
        assert paths.sync_state == vault / ".llm-wiki" / "sync-state.json"

    def test_vault_paths_custom_dirs(self, tmp_path: Path) -> None:
        from philip.wiki.config import VaultSection, WikiConfig, vault_paths

        config = WikiConfig(vault=VaultSection(source_dir="raw", wiki_dir="docs", pages_subdir=""))
        paths = vault_paths(tmp_path, config)

        assert paths.contexts == tmp_path / "raw"
        assert paths.wiki == tmp_path / "docs"
        assert paths.wiki_root == tmp_path / "docs"


# ---------------------------------------------------------------------------
# Wiki page tests
# ---------------------------------------------------------------------------


class TestWiki:
    def test_extract_wikilinks(self) -> None:
        from philip.wiki.wiki import extract_wikilinks

        content = "See [[raft-consensus]] and [[paxos|Paxos algorithm]]. Also [[raft-consensus]]."
        links = extract_wikilinks(content)
        assert links == ["raft-consensus", "paxos"]

    def test_extract_wikilinks_empty(self) -> None:
        from philip.wiki.wiki import extract_wikilinks

        assert extract_wikilinks("no links here") == []

    def test_extract_wikilinks_cjk(self) -> None:
        from philip.wiki.wiki import extract_wikilinks

        content = "参见 [[分布式一致性]] 和 [[Raft算法]]"
        links = extract_wikilinks(content)
        assert "分布式一致性" in links
        assert "Raft算法" in links

    def test_parse_wiki_page(self, vault: Path) -> None:
        from philip.wiki.wiki import parse_wiki_page

        page = parse_wiki_page(vault / "wiki" / "pages" / "raft-consensus.md", vault / "wiki" / "pages")
        assert page.title == "Raft Consensus"
        assert page.description == "A consensus algorithm for distributed systems"
        assert page.tags == ["concept", "distributed"]
        assert page.aliases == ["Raft"]
        assert page.slug == "raft-consensus"
        assert "leader-election" in page.wikilinks
        assert "log-replication" in page.wikilinks
        assert "paxos" in page.wikilinks

    def test_load_wiki_pages(self, vault: Path) -> None:
        from philip.wiki.wiki import load_wiki_pages

        pages = load_wiki_pages(vault / "wiki" / "pages")
        assert len(pages) == 4
        slugs = {p.slug for p in pages}
        assert "raft-consensus" in slugs
        assert "apache-kafka" in slugs

    def test_list_markdown_files(self, vault: Path) -> None:
        from philip.wiki.wiki import list_markdown_files

        files = list_markdown_files(vault / "wiki" / "pages")
        assert len(files) == 4
        assert all(f.suffix == ".md" for f in files)

    def test_list_markdown_files_nonexistent(self, tmp_path: Path) -> None:
        from philip.wiki.wiki import list_markdown_files

        assert list_markdown_files(tmp_path / "nonexistent") == []


# ---------------------------------------------------------------------------
# Search tests
# ---------------------------------------------------------------------------


class TestSearch:
    def test_tokenize_english(self) -> None:
        from philip.wiki.search import tokenize

        tokens = tokenize("Hello World Test")
        assert tokens == ["hello", "world", "test"]

    def test_tokenize_cjk(self) -> None:
        from philip.wiki.search import tokenize

        tokens = tokenize("分布式系统")
        # Unigrams: 分, 布, 式, 系, 统
        # Bigrams: 分布, 布式, 式系, 系统
        assert "分" in tokens
        assert "分布" in tokens
        assert "系统" in tokens

    def test_tokenize_mixed(self) -> None:
        from philip.wiki.search import tokenize

        tokens = tokenize("Kafka 分布式 streaming")
        assert "kafka" in tokens
        assert "分" in tokens
        assert "streaming" in tokens

    def test_tokenize_empty(self) -> None:
        from philip.wiki.search import tokenize

        assert tokenize("") == []

    def test_bm25_search_basic(self, vault: Path) -> None:
        from philip.wiki.search import bm25_search
        from philip.wiki.wiki import load_wiki_pages

        pages = load_wiki_pages(vault / "wiki" / "pages")
        results = bm25_search(pages, "consensus algorithm")
        assert len(results) > 0
        # raft-consensus should be top result
        assert results[0].page.slug == "raft-consensus"

    def test_bm25_search_cjk(self, tmp_path: Path) -> None:
        """Test BM25 with CJK content."""
        from philip.wiki.search import bm25_search
        from philip.wiki.wiki import WikiPage

        pages = [
            WikiPage(
                path=Path("a.md"),
                relative_path="a.md",
                slug="distributed-systems",
                title="分布式系统",
                content="分布式系统是一类多台计算机协同工作的系统。",
                mtime=0,
            ),
            WikiPage(
                path=Path("b.md"),
                relative_path="b.md",
                slug="web-development",
                title="Web Development",
                content="Building web applications with HTML, CSS, and JavaScript.",
                mtime=0,
            ),
        ]
        results = bm25_search(pages, "分布式")
        assert len(results) > 0
        assert results[0].page.slug == "distributed-systems"

    def test_bm25_search_no_results(self, vault: Path) -> None:
        from philip.wiki.search import bm25_search
        from philip.wiki.wiki import load_wiki_pages

        pages = load_wiki_pages(vault / "wiki" / "pages")
        results = bm25_search(pages, "quantum computing superposition")
        assert len(results) == 0

    def test_bm25_search_limit(self, vault: Path) -> None:
        from philip.wiki.search import bm25_search
        from philip.wiki.wiki import load_wiki_pages

        pages = load_wiki_pages(vault / "wiki" / "pages")
        results = bm25_search(pages, "consensus", limit=1)
        assert len(results) <= 1

    def test_bm25_search_empty_pages(self) -> None:
        from philip.wiki.search import bm25_search

        assert bm25_search([], "test") == []

    def test_rrf_merge(self) -> None:
        from philip.wiki.search import rrf_merge

        bm25 = [{"slug": "a", "score": 10.0}, {"slug": "b", "score": 5.0}]
        vector = [{"slug": "b", "score": 0.9}, {"slug": "c", "score": 0.8}]
        merged = rrf_merge(bm25, vector, limit=3)

        slugs = [r["slug"] for r in merged]
        # 'b' appears in both lists so should rank highest
        assert slugs[0] == "b"
        assert len(merged) == 3

    def test_rrf_merge_limit(self) -> None:
        from philip.wiki.search import rrf_merge

        bm25 = [{"slug": "a", "score": 1.0}, {"slug": "b", "score": 0.9}]
        vector = [{"slug": "c", "score": 0.8}]
        merged = rrf_merge(bm25, vector, limit=2)
        assert len(merged) == 2


# ---------------------------------------------------------------------------
# Graph tests
# ---------------------------------------------------------------------------


class TestGraph:
    def test_analyze_graph_basic(self, vault: Path) -> None:
        from philip.wiki.graph import analyze_graph
        from philip.wiki.wiki import load_wiki_pages

        pages = load_wiki_pages(vault / "wiki" / "pages")
        analysis = analyze_graph(pages)

        assert len(analysis.nodes) == 4
        assert len(analysis.edges) > 0
        # raft-consensus should be a hub (most incoming links)
        hub_slugs = [h.slug for h in analysis.hubs]
        assert "raft-consensus" in hub_slugs[:2]

    def test_analyze_graph_orphans(self, vault: Path) -> None:
        """Pages with no incoming links are orphans."""
        from philip.wiki.graph import analyze_graph
        from philip.wiki.wiki import load_wiki_pages

        pages = load_wiki_pages(vault / "wiki" / "pages")
        analysis = analyze_graph(pages)

        # leader-election has incoming from raft-consensus, so not orphan
        # But apache-kafka has incoming from nobody (raft-consensus doesn't link to it)
        # Actually, raft-consensus links to leader-election, log-replication, paxos
        # leader-election links to raft-consensus
        # log-replication links to raft-consensus
        # apache-kafka links to raft-consensus
        # So raft-consensus has 3 incoming, leader-election has 1, log-replication has 1
        # apache-kafka has 0 incoming -> orphan
        assert "apache-kafka" in analysis.orphans

    def test_analyze_graph_wanted_pages(self, vault: Path) -> None:
        """Wikilinks that don't resolve are wanted pages."""
        from philip.wiki.graph import analyze_graph
        from philip.wiki.wiki import load_wiki_pages

        pages = load_wiki_pages(vault / "wiki" / "pages")
        analysis = analyze_graph(pages)

        # raft-consensus links to "paxos" which doesn't exist
        assert "paxos" in analysis.wanted_pages

    def test_analyze_graph_communities(self, vault: Path) -> None:
        from philip.wiki.graph import analyze_graph
        from philip.wiki.wiki import load_wiki_pages

        pages = load_wiki_pages(vault / "wiki" / "pages")
        analysis = analyze_graph(pages)

        # All pages link to raft-consensus, so they should form at least one community
        total_community_members = sum(len(m) for m in analysis.communities.values())
        assert total_community_members > 0

    def test_analyze_graph_empty(self) -> None:
        from philip.wiki.graph import analyze_graph

        analysis = analyze_graph([])
        assert analysis.nodes == []
        assert analysis.edges == []
        assert analysis.orphans == []
        assert analysis.wanted_pages == {}
        assert analysis.hubs == []

    def test_analyze_graph_alias_resolution(self, tmp_path: Path) -> None:
        """Aliases should be used for link resolution."""
        from philip.wiki.graph import analyze_graph
        from philip.wiki.wiki import WikiPage

        pages = [
            WikiPage(
                path=Path("a.md"),
                relative_path="a.md",
                slug="raft-consensus",
                title="Raft",
                aliases=["Raft Algorithm"],
                content="See [[Raft Algorithm]]",
                wikilinks=["Raft Algorithm"],
                mtime=0,
            ),
            WikiPage(
                path=Path("b.md"),
                relative_path="b.md",
                slug="raft-algorithm",
                title="Raft Algorithm",
                aliases=[],
                content="",
                wikilinks=[],
                mtime=0,
            ),
        ]
        analysis = analyze_graph(pages)
        # Should resolve "Raft Algorithm" alias -> raft-algorithm
        assert len(analysis.edges) == 1
        assert analysis.edges[0].dst == "raft-algorithm"


# ---------------------------------------------------------------------------
# Sync tests
# ---------------------------------------------------------------------------


class TestSync:
    def test_load_sync_state_empty(self, tmp_path: Path) -> None:
        from philip.wiki.sync import load_sync_state

        state = load_sync_state(tmp_path / "nonexistent.json")
        assert state.entries == {}
        assert state.last_sync == ""

    def test_save_and_load_sync_state(self, tmp_path: Path) -> None:
        from philip.wiki.sync import SyncEntry, SyncState, load_sync_state, save_sync_state

        state = SyncState(
            entries={
                "wiki/test.md": SyncEntry(
                    path="wiki/test.md", mtime=12345.0, content_hash="abc123", last_synced="2026-01-01"
                )
            },
            last_sync="2026-01-01",
        )
        state_path = tmp_path / "sync.json"
        save_sync_state(state_path, state)

        loaded = load_sync_state(state_path)
        assert loaded.last_sync == "2026-01-01"
        assert "wiki/test.md" in loaded.entries
        assert loaded.entries["wiki/test.md"].content_hash == "abc123"

    def test_content_hash(self, tmp_path: Path) -> None:
        from philip.wiki.sync import content_hash

        f = tmp_path / "test.md"
        f.write_text("Hello, world!", encoding="utf-8")
        h = content_hash(f)
        assert len(h) == 16
        # Same content -> same hash
        assert content_hash(f) == h

    def test_content_hash_different_content(self, tmp_path: Path) -> None:
        from philip.wiki.sync import content_hash

        a = tmp_path / "a.md"
        b = tmp_path / "b.md"
        a.write_text("Hello", encoding="utf-8")
        b.write_text("World", encoding="utf-8")
        assert content_hash(a) != content_hash(b)

    def test_compute_sync_added(self, vault: Path) -> None:
        from philip.wiki.sync import SyncState, compute_sync

        state = SyncState()
        result = compute_sync([vault / "wiki" / "pages"], vault, state)
        assert len(result.added) == 4
        assert len(result.modified) == 0
        assert len(result.deleted) == 0

    def test_compute_sync_unchanged(self, vault: Path) -> None:
        from philip.wiki.sync import (
            SyncState,
            compute_sync,
            update_sync_state,
        )

        # First sync: all added
        state = SyncState()
        new_state = update_sync_state([vault / "wiki" / "pages"], vault, state)

        # Second sync: all unchanged
        result = compute_sync([vault / "wiki" / "pages"], vault, new_state)
        assert len(result.added) == 0
        assert len(result.modified) == 0
        assert len(result.unchanged) == 4

    def test_compute_sync_modified(self, vault: Path) -> None:
        import time

        from philip.wiki.sync import (
            SyncState,
            compute_sync,
            update_sync_state,
        )

        # Sync once
        state = SyncState()
        new_state = update_sync_state([vault / "wiki" / "pages"], vault, state)

        # Modify a file
        time.sleep(0.01)  # ensure different mtime
        (vault / "wiki" / "pages" / "raft-consensus.md").write_text(
            "---\ntitle: Raft\n---\nUpdated content.\n",
            encoding="utf-8",
        )

        result = compute_sync([vault / "wiki" / "pages"], vault, new_state)
        assert len(result.modified) == 1
        assert "wiki/pages/raft-consensus.md" in result.modified

    def test_compute_sync_deleted(self, vault: Path) -> None:
        from philip.wiki.sync import (
            SyncState,
            compute_sync,
            update_sync_state,
        )

        # Sync once
        state = SyncState()
        new_state = update_sync_state([vault / "wiki" / "pages"], vault, state)

        # Delete a file
        (vault / "wiki" / "pages" / "apache-kafka.md").unlink()

        result = compute_sync([vault / "wiki" / "pages"], vault, new_state)
        assert len(result.deleted) == 1
        assert "wiki/pages/apache-kafka.md" in result.deleted


# ---------------------------------------------------------------------------
# Skills tests
# ---------------------------------------------------------------------------


class TestSkills:
    def test_list_skills(self) -> None:
        from philip.wiki.skills import list_skills

        skills = list_skills()
        assert "llm-wiki" in skills

    def test_install_skills_to(self, tmp_path: Path) -> None:
        from philip.wiki.skills import install_skills_to

        target = tmp_path / "installed"
        result = install_skills_to(target)
        assert "llm-wiki" in result.installed
        assert (target / "llm-wiki" / "SKILL.md").exists()

    def test_install_skills_no_overwrite(self, tmp_path: Path) -> None:
        from philip.wiki.skills import install_skills_to

        target = tmp_path / "installed"

        # First install
        result1 = install_skills_to(target, overwrite=False)
        assert "llm-wiki" in result1.installed

        # Second install with no overwrite
        result2 = install_skills_to(target, overwrite=False)
        assert "llm-wiki" in result2.skipped
        assert "llm-wiki" not in result2.installed
