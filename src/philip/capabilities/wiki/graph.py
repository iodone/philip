"""Wikilink graph analysis — communities, hubs, orphans, wanted pages."""

from __future__ import annotations

import random
from dataclasses import dataclass

from philip.capabilities.wiki.wiki import WikiPage

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class GraphNode:
    slug: str
    title: str
    tags: list[str]
    link_count: int
    incoming_count: int


@dataclass
class GraphEdge:
    src: str
    dst: str


@dataclass
class GraphAnalysis:
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    orphans: list[str]
    wanted_pages: dict[str, list[str]]  # target -> [referencing pages]
    communities: dict[str, list[str]]  # label -> [member slugs]
    hubs: list[GraphNode]


# ---------------------------------------------------------------------------
# Link resolution
# ---------------------------------------------------------------------------


def _normalize_key(name: str) -> str:
    """Normalize a name for slug matching: lowercase, spaces to hyphens."""
    return name.lower().replace(" ", "-")


def _build_slug_map(pages: list[WikiPage]) -> dict[str, str]:
    """Build a normalized name -> slug lookup map."""
    slug_map: dict[str, str] = {}
    for p in pages:
        slug_map[p.slug.lower()] = p.slug
        # Also map by last path segment (filename)
        filename = p.slug.rsplit("/", 1)[-1].lower()
        slug_map.setdefault(filename, p.slug)
        # Map aliases (normalized: spaces -> hyphens)
        for alias in p.aliases:
            slug_map.setdefault(_normalize_key(alias), p.slug)
    return slug_map


def _resolve_link(target: str, slug_map: dict[str, str]) -> str | None:
    lower = target.lower().removesuffix(".md")
    return slug_map.get(lower) or slug_map.get(
        _normalize_key(target.removesuffix(".md"))
    )


# ---------------------------------------------------------------------------
# Community detection (simplified label propagation)
# ---------------------------------------------------------------------------


def _detect_communities(
    pages: list[WikiPage],
    edges: list[GraphEdge],
) -> dict[str, list[str]]:
    """Simplified label propagation: max 10 rounds, majority-vote neighbor labels."""
    # Build adjacency list
    adj: dict[str, set[str]] = {p.slug: set() for p in pages}
    for edge in edges:
        adj.setdefault(edge.src, set()).add(edge.dst)
        adj.setdefault(edge.dst, set()).add(edge.src)

    # Initialize: each node is its own community
    labels: dict[str, str] = {p.slug: p.slug for p in pages}

    for _round in range(10):
        changed = False
        order = list(pages)
        random.shuffle(order)

        for page in order:
            neighbors = adj.get(page.slug)
            if not neighbors:
                continue

            # Count neighbor labels
            label_counts: dict[str, int] = {}
            for nb in neighbors:
                lbl = labels[nb]
                label_counts[lbl] = label_counts.get(lbl, 0) + 1

            # Pick most frequent label
            max_label = labels[page.slug]
            max_count = 0
            for lbl, cnt in label_counts.items():
                if cnt > max_count:
                    max_count = cnt
                    max_label = lbl

            if labels[page.slug] != max_label:
                labels[page.slug] = max_label
                changed = True

        if not changed:
            break

    # Group by label
    communities: dict[str, list[str]] = {}
    for slug, label in labels.items():
        communities.setdefault(label, []).append(slug)

    # Filter out single-node communities
    return {lbl: members for lbl, members in communities.items() if len(members) > 1}


# ---------------------------------------------------------------------------
# Graph analysis
# ---------------------------------------------------------------------------


def analyze_graph(pages: list[WikiPage]) -> GraphAnalysis:
    """Build a link graph from wiki pages and analyze it."""
    slug_map = _build_slug_map(pages)

    edges: list[GraphEdge] = []
    incoming: dict[str, set[str]] = {}

    for page in pages:
        for link in page.wikilinks:
            resolved = _resolve_link(link, slug_map)
            if resolved and resolved != page.slug:
                edges.append(GraphEdge(src=page.slug, dst=resolved))
                incoming.setdefault(resolved, set()).add(page.slug)

    # Wanted pages: wikilinks that don't resolve
    wanted_pages: dict[str, list[str]] = {}
    for page in pages:
        for link in page.wikilinks:
            if not _resolve_link(link, slug_map):
                wanted_pages.setdefault(link, []).append(page.slug)

    # Build nodes
    nodes = [
        GraphNode(
            slug=p.slug,
            title=p.title,
            tags=p.tags,
            link_count=len(p.wikilinks),
            incoming_count=len(incoming.get(p.slug, set())),
        )
        for p in pages
    ]

    # Orphans: pages with no incoming links
    orphans = [n.slug for n in nodes if n.incoming_count == 0]

    # Hubs: top 10 by total connections (incoming + outgoing)
    hubs = sorted(nodes, key=lambda n: n.link_count + n.incoming_count, reverse=True)[
        :10
    ]

    # Communities
    communities = _detect_communities(pages, edges)

    return GraphAnalysis(
        nodes=nodes,
        edges=edges,
        orphans=orphans,
        wanted_pages=wanted_pages,
        communities=communities,
        hubs=hubs,
    )
