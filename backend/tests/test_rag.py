"""Tests for pure functions in services/rag.py.

All tests here are fully offline — no Ollama, no ChromaDB, no filesystem I/O
beyond what is explicitly set up in each test.
"""

import tempfile
from pathlib import Path
from unittest.mock import Mock

import pytest

from services.rag import (
    RAGService,
    _BankHTMLExtractor,
    _mmr_rerank,
    _rrf,
    chunk_text,
    extract_html_text,
    get_html_files,
)


# ---------------------------------------------------------------------------
# HTML extraction
# ---------------------------------------------------------------------------

class TestBankHTMLExtractor:
    def _extract(self, html: str) -> tuple[str, str]:
        parser = _BankHTMLExtractor()
        parser.feed(html)
        return parser.title, parser.get_text()

    def test_extracts_title(self):
        _, text = self._extract("<html><head><title>Credite</title></head><body><p>Info</p></body></html>")
        # title is captured separately
        parser = _BankHTMLExtractor()
        parser.feed("<html><head><title>Credite</title></head><body><p>Info</p></body></html>")
        assert parser.title == "Credite"

    def test_extracts_paragraph_text(self):
        _, text = self._extract("<html><body><p>Hello world</p></body></html>")
        assert "Hello world" in text

    def test_strips_nav(self):
        _, text = self._extract("<html><body><nav>Skip me</nav><p>Keep me</p></body></html>")
        assert "Skip me" not in text
        assert "Keep me" in text

    def test_strips_header(self):
        _, text = self._extract("<html><body><header>Header text</header><p>Body text</p></body></html>")
        assert "Header text" not in text
        assert "Body text" in text

    def test_strips_footer(self):
        _, text = self._extract("<html><body><footer>Footer</footer><p>Content</p></body></html>")
        assert "Footer" not in text
        assert "Content" in text

    def test_strips_script(self):
        _, text = self._extract("<html><body><script>var x=1;</script><p>Text</p></body></html>")
        assert "var x" not in text
        assert "Text" in text

    def test_strips_style(self):
        _, text = self._extract("<html><body><style>.cls{color:red}</style><p>Text</p></body></html>")
        assert ".cls" not in text
        assert "Text" in text

    def test_extracts_list_items(self):
        _, text = self._extract("<html><body><ul><li>Item one</li><li>Item two</li></ul></body></html>")
        assert "Item one" in text
        assert "Item two" in text

    def test_empty_html(self):
        _, text = self._extract("")
        assert text == ""

    def test_multiple_paragraphs_separated(self):
        _, text = self._extract("<html><body><p>First</p><p>Second</p></body></html>")
        assert "First" in text
        assert "Second" in text


class TestExtractHtmlText:
    def test_reads_file(self, tmp_path):
        f = tmp_path / "page.html"
        f.write_text("<html><head><title>Test</title></head><body><p>Hello</p></body></html>")
        title, text = extract_html_text(f)
        assert title == "Test"
        assert "Hello" in text

    def test_returns_empty_on_missing_file(self, tmp_path):
        title, text = extract_html_text(tmp_path / "nonexistent.html")
        assert title == ""
        assert text == ""

    def test_handles_encoding_errors_gracefully(self, tmp_path):
        f = tmp_path / "page.html"
        f.write_bytes(b"<html><body><p>Caf\xe9</p></body></html>")  # latin-1 byte
        title, text = extract_html_text(f)
        # Should not raise; content may be partial
        assert isinstance(text, str)


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

class TestChunkText:
    def test_short_text_produces_one_chunk(self):
        chunks = chunk_text("Hello world", "test.html", "Title", 800, 80)
        assert len(chunks) == 1

    def test_long_text_produces_multiple_chunks(self):
        text = " ".join(["word"] * 500)
        chunks = chunk_text(text, "test.html", "Title", 100, 10)
        assert len(chunks) > 1

    def test_first_chunk_has_title_prefix(self):
        chunks = chunk_text("Hello world", "test.html", "My Title", 800, 80)
        assert chunks[0]["text"].startswith("My Title: ")

    def test_subsequent_chunks_have_no_title_prefix(self):
        text = " ".join(["word"] * 500)
        chunks = chunk_text(text, "test.html", "Title", 100, 10)
        assert len(chunks) > 1
        assert not chunks[1]["text"].startswith("Title: ")

    def test_chunk_index_increments(self):
        text = " ".join(["word"] * 500)
        chunks = chunk_text(text, "test.html", "Title", 100, 10)
        indices = [c["chunk_index"] for c in chunks]
        assert indices == list(range(len(chunks)))

    def test_source_preserved_in_all_chunks(self):
        text = " ".join(["word"] * 500)
        chunks = chunk_text(text, "credite/page.html", "Title", 100, 10)
        assert all(c["source"] == "credite/page.html" for c in chunks)

    def test_no_chunks_for_empty_text(self):
        chunks = chunk_text("", "test.html", "Title", 800, 80)
        assert chunks == []

    def test_chunks_do_not_exceed_size_by_much(self):
        text = " ".join(["word"] * 1000)
        chunks = chunk_text(text, "test.html", "Title", 200, 20)
        # Each chunk should be within a word's length of the target size
        for c in chunks:
            assert len(c["text"]) <= 220


# ---------------------------------------------------------------------------
# RRF fusion
# ---------------------------------------------------------------------------

class TestRRF:
    def test_single_list_preserves_order(self):
        result = _rrf([["a", "b", "c"]])
        assert result == ["a", "b", "c"]

    def test_items_in_both_lists_rank_higher(self):
        # "b" appears at rank 0 in both lists — highest combined score
        result = _rrf([["b", "a", "c"], ["b", "c", "a"]])
        assert result[0] == "b"

    def test_all_ids_present_in_result(self):
        result = _rrf([["a", "b"], ["c", "d"]])
        assert set(result) == {"a", "b", "c", "d"}

    def test_empty_lists_return_empty(self):
        result = _rrf([[], []])
        assert result == []

    def test_duplicate_ids_not_doubled(self):
        result = _rrf([["a", "b"], ["a", "b"]])
        assert result.count("a") == 1
        assert result.count("b") == 1


# ---------------------------------------------------------------------------
# MMR reranking
# ---------------------------------------------------------------------------

class TestMMRRerank:
    def _make_candidates(self, items: list[tuple[str, str, float]]):
        return [(text, {"title": title}, score) for text, title, score in items]

    def test_returns_exactly_top_k(self):
        candidates = self._make_candidates([
            ("credit loan bank", "A", 0.9),
            ("debit card payment", "B", 0.8),
            ("savings deposit", "C", 0.7),
            ("investment fund", "D", 0.6),
        ])
        result = _mmr_rerank(candidates, {"credit"}, top_k=2, lam=0.7)
        assert len(result) == 2

    def test_returns_fewer_when_candidates_insufficient(self):
        candidates = self._make_candidates([("text", "A", 0.9)])
        result = _mmr_rerank(candidates, {"text"}, top_k=5, lam=0.7)
        assert len(result) == 1

    def test_avoids_redundant_chunks(self):
        # A and B are near-identical; C is diverse.
        # With lambda=0.7, after picking A, C should beat B.
        candidates = self._make_candidates([
            ("credit loan interest rate mortgage bank", "A", 0.9),
            ("credit loan interest rate mortgage bank", "B", 0.85),
            ("savings deposit term account yield", "C", 0.5),
        ])
        result = _mmr_rerank(candidates, {"credit"}, top_k=2, lam=0.7)
        titles = [m["title"] for _, m in result]
        assert "A" in titles
        assert "C" in titles

    def test_result_contains_text_and_metadata(self):
        candidates = self._make_candidates([("hello world", "Page", 0.9)])
        result = _mmr_rerank(candidates, {"hello"}, top_k=1, lam=0.7)
        text, meta = result[0]
        assert isinstance(text, str)
        assert isinstance(meta, dict)


# ---------------------------------------------------------------------------
# File discovery
# ---------------------------------------------------------------------------

class TestGetHtmlFiles:
    def test_finds_html_files(self, tmp_path):
        (tmp_path / "page.html").write_text("<html></html>")
        files = get_html_files(tmp_path)
        assert len(files) == 1

    def test_excludes_en_directory(self, tmp_path):
        en = tmp_path / "en"
        en.mkdir()
        (en / "page.html").write_text("<html></html>")
        files = get_html_files(tmp_path)
        assert files == []

    def test_excludes_ru_directory(self, tmp_path):
        ru = tmp_path / "ru"
        ru.mkdir()
        (ru / "page.html").write_text("<html></html>")
        assert get_html_files(tmp_path) == []

    def test_excludes_themes_directory(self, tmp_path):
        themes = tmp_path / "themes"
        themes.mkdir()
        (themes / "page.html").write_text("<html></html>")
        assert get_html_files(tmp_path) == []

    def test_includes_non_excluded_directories(self, tmp_path):
        credite = tmp_path / "credite"
        credite.mkdir()
        (credite / "page.html").write_text("<html></html>")
        files = get_html_files(tmp_path)
        assert len(files) == 1

    def test_does_not_include_non_html_files(self, tmp_path):
        (tmp_path / "robots.txt").write_text("User-agent: *")
        (tmp_path / "image.webp").write_bytes(b"\x00")
        assert get_html_files(tmp_path) == []

    def test_finds_nested_html_files(self, tmp_path):
        sub = tmp_path / "credite" / "consum"
        sub.mkdir(parents=True)
        (sub / "page.html").write_text("<html></html>")
        files = get_html_files(tmp_path)
        assert len(files) == 1


# ---------------------------------------------------------------------------
# RAGService.retrieve() — failure modes
# ---------------------------------------------------------------------------

class TestRAGServiceRetrieveFailureModes:
    """retrieve() must always return ([], []) instead of propagating exceptions.

    All I/O is replaced with lightweight mocks — no real Ollama or ChromaDB.
    """

    @pytest.fixture
    def rag(self):
        svc = RAGService()
        yield svc
        # Close HTTP clients synchronously (fine for tests that never open them)
        svc._http_client.close()

    async def test_embedding_failure_returns_empty(self, rag):
        """When _embed raises, retrieve() degrades gracefully to ([], [])."""
        mock_col = Mock()
        mock_col.query.return_value = {"ids": [[]], "documents": [[]], "metadatas": [[]]}
        rag._get_collection = Mock(return_value=mock_col)
        rag._embed = Mock(side_effect=RuntimeError("Ollama embed endpoint down"))

        result = await rag.retrieve("carduri de debit")

        assert result == ([], [])

    async def test_chromadb_unavailable_returns_empty(self, rag):
        """When _get_collection raises (ChromaDB not running), returns ([], [])."""
        rag._get_collection = Mock(side_effect=RuntimeError("ChromaDB not reachable"))

        result = await rag.retrieve("credite")

        assert result == ([], [])

    async def test_empty_collection_returns_empty(self, rag):
        """An empty ChromaDB collection (no docs indexed) returns ([], [])."""
        mock_col = Mock()
        mock_col.query.return_value = {"ids": [[]], "documents": [[]], "metadatas": [[]]}
        rag._get_collection = Mock(return_value=mock_col)
        rag._embed = Mock(return_value=[[0.1] * 10])
        # BM25 index is None by default → BM25 leg is skipped

        result = await rag.retrieve("orice întrebare")

        assert result == ([], [])
