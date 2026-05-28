"""DB9 — PostgreSQL vector search client for wiki index management.

Uses pgvector for HNSW cosine similarity search with server-side embeddings.
Optional dependency: requires ``pg`` (psycopg2) or ``asyncpg`` to be installed,
and a PostgreSQL instance with the ``vector`` extension enabled.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from philip.capabilities.wiki.config import WikiConfig
from philip.capabilities.wiki.wiki import WikiPage

# ---------------------------------------------------------------------------
# Lazy import for psycopg2
# ---------------------------------------------------------------------------


def _load_psycopg2() -> Any:
    """Import psycopg2 at runtime (optional dependency)."""
    try:
        import psycopg2

        return psycopg2
    except ModuleNotFoundError:
        raise RuntimeError(
            "psycopg2 is required for DB9 integration. "
            "Install it with: pip install philip[db9]"
        ) from None


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class DB9SearchResult:
    slug: str
    title: str
    similarity: float


# ---------------------------------------------------------------------------
# DB9 Client
# ---------------------------------------------------------------------------


class DB9Client:
    """PostgreSQL + pgvector client for wiki index management.

    Uses DB9's built-in ``embedding()`` function for server-side embeddings.
    """

    def __init__(self, url: str) -> None:
        self._url = url
        self._conn: Any = None

    def _get_conn(self) -> Any:
        if self._conn is None:
            psycopg2 = _load_psycopg2()
            self._conn = psycopg2.connect(self._url)
        return self._conn

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    # ------------------------------------------------------------------
    # Schema management
    # ------------------------------------------------------------------

    def ensure_schema(self) -> None:
        """Create wiki_index and wiki_page_sources tables if they don't exist."""
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS wiki_index (
                slug TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT,
                content TEXT NOT NULL,
                tags TEXT[] DEFAULT '{}',
                contexts TEXT[] DEFAULT '{}',
                content_hash TEXT NOT NULL,
                updated TEXT,
                embedding VECTOR(1024)
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS wiki_page_contexts (
                slug TEXT NOT NULL,
                context_path TEXT NOT NULL,
                PRIMARY KEY (slug, context_path)
            )
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_wiki_embedding
            ON wiki_index USING hnsw (embedding vector_cosine_ops)
        """)
        conn.commit()
        cur.close()

    # ------------------------------------------------------------------
    # Page CRUD
    # ------------------------------------------------------------------

    def upsert_page(self, page: WikiPage, content_hash: str) -> None:
        """Insert or update a wiki page with server-side embedding."""
        conn = self._get_conn()
        cur = conn.cursor()
        embedding_text = f"{page.title}. {page.description or ''}. {page.content}"

        cur.execute(
            """
            INSERT INTO wiki_index
                (slug, title, description, content, tags,
                 contexts, content_hash, updated, embedding)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s,
                    embedding(%s)::vector(1024))
            ON CONFLICT (slug) DO UPDATE SET
                title = EXCLUDED.title,
                description = EXCLUDED.description,
                content = EXCLUDED.content,
                tags = EXCLUDED.tags,
                contexts = EXCLUDED.contexts,
                content_hash = EXCLUDED.content_hash,
                updated = EXCLUDED.updated,
                embedding = EXCLUDED.embedding
            """,
            [
                page.slug,
                page.title,
                page.description or "",
                page.content,
                page.tags,
                page.contexts,
                content_hash,
                page.updated or "",
                embedding_text,
            ],
        )

        # Rebuild context mappings
        cur.execute("DELETE FROM wiki_page_contexts WHERE slug = %s", (page.slug,))
        for ctx in page.contexts:
            cur.execute(
                "INSERT INTO wiki_page_contexts"
                " (slug, context_path)"
                " VALUES (%s, %s) ON CONFLICT DO NOTHING",
                (page.slug, ctx),
            )
        conn.commit()
        cur.close()

    def delete_page(self, slug: str) -> None:
        """Remove a wiki page and its context mappings from the index."""
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute("DELETE FROM wiki_page_contexts WHERE slug = %s", (slug,))
        cur.execute("DELETE FROM wiki_index WHERE slug = %s", (slug,))
        conn.commit()
        cur.close()

    # ------------------------------------------------------------------
    # Vector search
    # ------------------------------------------------------------------

    def vector_search(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """Run cosine similarity search using server-side embeddings."""
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute(
            """
            WITH q AS (SELECT embedding(%s)::vector(1024) AS qv)
            SELECT slug, title, 1 - (embedding <=> q.qv) AS similarity
            FROM wiki_index, q
            WHERE embedding IS NOT NULL
            ORDER BY embedding <=> q.qv
            LIMIT %s
            """,
            (query, limit),
        )
        rows = cur.fetchall()
        cur.close()
        return [
            {"slug": row[0], "title": row[1], "similarity": float(row[2])}
            for row in rows
        ]

    # ------------------------------------------------------------------
    # Hash management
    # ------------------------------------------------------------------

    def get_content_hash(self, slug: str) -> str | None:
        """Get the stored content hash for a page."""
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute("SELECT content_hash FROM wiki_index WHERE slug = %s", (slug,))
        row = cur.fetchone()
        cur.close()
        return row[0] if row else None

    def get_all_hashes(self) -> dict[str, str]:
        """Get all slug -> content_hash mappings."""
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute("SELECT slug, content_hash FROM wiki_index")
        rows = cur.fetchall()
        cur.close()
        return {row[0]: row[1] for row in rows}

    def pages_by_context(self, context_path: str) -> list[str]:
        """Get all page slugs that reference a given context path."""
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT slug FROM wiki_page_contexts WHERE context_path = %s",
            (context_path,),
        )
        rows = cur.fetchall()
        cur.close()
        return [row[0] for row in rows]


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def create_db9_client(config: WikiConfig) -> DB9Client | None:
    """Create a DB9 client from config, or None if not configured."""
    if not config.db9 or not config.db9.url:
        return None
    return DB9Client(url=config.db9.url)
