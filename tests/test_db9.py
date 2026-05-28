"""Tests for philip.capabilities.wiki.db9 — PostgreSQL vector search client (mocked)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from philip.capabilities.wiki.config import DB9Section, VaultSection, WikiConfig
from philip.capabilities.wiki.wiki import WikiPage

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_psycopg2():
    """Mock psycopg2 module for testing without a real database."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor

    with patch("philip.capabilities.wiki.db9._load_psycopg2") as mock_load:
        mock_pg = MagicMock()
        mock_pg.connect.return_value = mock_conn
        mock_load.return_value = mock_pg
        yield {
            "psycopg2": mock_pg,
            "conn": mock_conn,
            "cursor": mock_cursor,
            "connect": mock_pg.connect,
        }


@pytest.fixture
def db9_config():
    """Config with DB9 enabled."""
    return WikiConfig(
        vault=VaultSection(),
        db9=DB9Section(url="postgresql://localhost/test"),
    )


@pytest.fixture
def sample_page():
    """A sample WikiPage for testing."""
    return WikiPage(
        path=Path("wiki/pages/test.md"),
        relative_path="wiki/pages/test.md",
        slug="test",
        title="Test Page",
        description="A test page for unit testing",
        tags=["test", "example"],
        contexts=["contexts/test.txt"],
        content="This is the test content.",
        wikilinks=["other-page"],
        mtime=1234567890.0,
        created="2026-01-01",
        updated="2026-05-21",
    )


# ---------------------------------------------------------------------------
# Factory tests
# ---------------------------------------------------------------------------


class TestCreateDB9Client:
    def test_returns_client_when_configured(self, db9_config):
        from philip.capabilities.wiki.db9 import create_db9_client

        client = create_db9_client(db9_config)
        assert client is not None
        client.close()

    def test_returns_none_when_no_db9(self):
        from philip.capabilities.wiki.db9 import create_db9_client

        config = WikiConfig(vault=VaultSection())
        assert create_db9_client(config) is None

    def test_returns_none_when_empty_url(self):
        from philip.capabilities.wiki.db9 import create_db9_client

        config = WikiConfig(vault=VaultSection(), db9=DB9Section(url=""))
        assert create_db9_client(config) is None


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------


class TestDB9Schema:
    def test_ensure_schema_creates_tables(self, mock_psycopg2, db9_config):
        from philip.capabilities.wiki.db9 import create_db9_client

        client = create_db9_client(db9_config)
        client.ensure_schema()

        cursor = mock_psycopg2["cursor"]
        assert cursor.execute.call_count == 3
        calls = [str(c) for c in cursor.execute.call_args_list]
        assert any("wiki_index" in c for c in calls)
        assert any("wiki_page_contexts" in c for c in calls)
        assert any("idx_wiki_embedding" in c for c in calls)


# ---------------------------------------------------------------------------
# Page CRUD tests
# ---------------------------------------------------------------------------


class TestDB9PageCRUD:
    def test_upsert_page(self, mock_psycopg2, db9_config, sample_page):
        from philip.capabilities.wiki.db9 import create_db9_client

        client = create_db9_client(db9_config)
        client.upsert_page(sample_page, "abc123hash")

        cursor = mock_psycopg2["cursor"]
        # Should execute: INSERT/ON CONFLICT, DELETE old contexts, INSERT new context
        assert cursor.execute.call_count >= 3

        # Check the main upsert call
        main_call = cursor.execute.call_args_list[0]
        assert "INSERT INTO wiki_index" in str(main_call)
        assert main_call[0][1][0] == "test"  # slug
        assert main_call[0][1][1] == "Test Page"  # title
        assert main_call[0][1][6] == "abc123hash"  # content_hash

    def test_delete_page(self, mock_psycopg2, db9_config):
        from philip.capabilities.wiki.db9 import create_db9_client

        client = create_db9_client(db9_config)
        client.delete_page("test-slug")

        cursor = mock_psycopg2["cursor"]
        assert cursor.execute.call_count == 2
        # First call: DELETE from wiki_page_contexts
        assert "wiki_page_contexts" in str(cursor.execute.call_args_list[0])
        # Second call: DELETE from wiki_index
        assert "wiki_index" in str(cursor.execute.call_args_list[1])


# ---------------------------------------------------------------------------
# Vector search tests
# ---------------------------------------------------------------------------


class TestDB9VectorSearch:
    def test_vector_search(self, mock_psycopg2, db9_config):
        from philip.capabilities.wiki.db9 import create_db9_client

        # Mock cursor.fetchall() to return search results
        mock_psycopg2["cursor"].fetchall.return_value = [
            ("test-page", "Test Page", 0.85),
            ("other-page", "Other Page", 0.72),
        ]

        client = create_db9_client(db9_config)
        results = client.vector_search("test query", limit=10)

        assert len(results) == 2
        assert results[0]["slug"] == "test-page"
        assert results[0]["title"] == "Test Page"
        assert results[0]["similarity"] == pytest.approx(0.85)
        assert results[1]["slug"] == "other-page"

    def test_vector_search_empty(self, mock_psycopg2, db9_config):
        from philip.capabilities.wiki.db9 import create_db9_client

        mock_psycopg2["cursor"].fetchall.return_value = []

        client = create_db9_client(db9_config)
        results = client.vector_search("no matches")
        assert results == []


# ---------------------------------------------------------------------------
# Hash management tests
# ---------------------------------------------------------------------------


class TestDB9HashManagement:
    def test_get_content_hash(self, mock_psycopg2, db9_config):
        from philip.capabilities.wiki.db9 import create_db9_client

        mock_psycopg2["cursor"].fetchone.return_value = ("abc123def456",)

        client = create_db9_client(db9_config)
        h = client.get_content_hash("test-slug")

        assert h == "abc123def456"
        assert "SELECT content_hash" in str(mock_psycopg2["cursor"].execute.call_args)

    def test_get_content_hash_not_found(self, mock_psycopg2, db9_config):
        from philip.capabilities.wiki.db9 import create_db9_client

        mock_psycopg2["cursor"].fetchone.return_value = None

        client = create_db9_client(db9_config)
        h = client.get_content_hash("nonexistent")
        assert h is None

    def test_get_all_hashes(self, mock_psycopg2, db9_config):
        from philip.capabilities.wiki.db9 import create_db9_client

        mock_psycopg2["cursor"].fetchall.return_value = [
            ("page-a", "hash_a"),
            ("page-b", "hash_b"),
        ]

        client = create_db9_client(db9_config)
        hashes = client.get_all_hashes()

        assert hashes == {"page-a": "hash_a", "page-b": "hash_b"}

    def test_pages_by_context(self, mock_psycopg2, db9_config):
        from philip.capabilities.wiki.db9 import create_db9_client

        mock_psycopg2["cursor"].fetchall.return_value = [
            ("page-1",),
            ("page-2",),
        ]

        client = create_db9_client(db9_config)
        slugs = client.pages_by_context("contexts/test.txt")

        assert slugs == ["page-1", "page-2"]


# ---------------------------------------------------------------------------
# Connection lifecycle tests
# ---------------------------------------------------------------------------


class TestDB9Connection:
    def test_lazy_connection(self, mock_psycopg2, db9_config):
        """Connection is established on first use, not on construction."""
        from philip.capabilities.wiki.db9 import create_db9_client

        client = create_db9_client(db9_config)
        # No connection yet
        mock_psycopg2["connect"].assert_not_called()

        # First operation triggers connection
        client.get_content_hash("test")
        mock_psycopg2["connect"].assert_called_once()

    def test_close(self, mock_psycopg2, db9_config):
        from philip.capabilities.wiki.db9 import create_db9_client

        client = create_db9_client(db9_config)
        client.get_content_hash("test")  # trigger connection
        client.close()

        mock_psycopg2["conn"].close.assert_called_once()

    def test_close_noop_when_not_connected(self, mock_psycopg2, db9_config):
        from philip.capabilities.wiki.db9 import create_db9_client

        client = create_db9_client(db9_config)
        # Close without ever connecting
        client.close()
        mock_psycopg2["conn"].close.assert_not_called()


# ---------------------------------------------------------------------------
# Error handling tests
# ---------------------------------------------------------------------------


class TestDB9Errors:
    def test_psycopg2_not_installed(self, db9_config):
        from philip.capabilities.wiki.db9 import _load_psycopg2

        with patch.dict("sys.modules", {"psycopg2": None}):
            with pytest.raises(RuntimeError, match="psycopg2 is required"):
                _load_psycopg2()
