"""Philip Wiki — agent-native knowledge base (Python port of llm-wiki)."""

from __future__ import annotations

from philip.wiki.config import WikiConfig, find_vault_root, load_config, vault_paths
from philip.wiki.db9 import DB9Client, DB9SearchResult, create_db9_client
from philip.wiki.wiki import WikiPage, extract_wikilinks, load_wiki_pages, parse_wiki_page
from philip.wiki.search import bm25_search, rrf_merge, tokenize
from philip.wiki.graph import GraphAnalysis, analyze_graph
from philip.wiki.sync import SyncResult, SyncState, compute_sync, load_sync_state, save_sync_state, update_sync_state
from philip.wiki.skills import install_skills_to, list_skills

__all__ = [
    # config
    "WikiConfig",
    "find_vault_root",
    "load_config",
    "vault_paths",
    # db9
    "DB9Client",
    "DB9SearchResult",
    "create_db9_client",
    # wiki
    "WikiPage",
    "extract_wikilinks",
    "load_wiki_pages",
    "parse_wiki_page",
    # search
    "tokenize",
    "bm25_search",
    "rrf_merge",
    # graph
    "GraphAnalysis",
    "analyze_graph",
    # sync
    "SyncResult",
    "SyncState",
    "compute_sync",
    "load_sync_state",
    "save_sync_state",
    "update_sync_state",
    # skills
    "install_skills_to",
    "list_skills",
]
