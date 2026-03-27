"""Unit tests for Pydantic field validators in config.Settings."""
import pytest
from pydantic import ValidationError

from config import Settings


class TestSettingsValidators:
    def _make(self, **overrides) -> Settings:
        """Build a Settings object with safe defaults and the given overrides."""
        defaults = {
            "data_path": "/tmp",
            "chroma_path": "/tmp/chroma",
            "bm25_cache_path": "/tmp/bm25.pkl",
        }
        defaults.update(overrides)
        return Settings(**defaults)

    # --- positive-int fields ---

    def test_rag_top_k_zero_raises(self):
        with pytest.raises(ValidationError, match="rag_top_k"):
            self._make(rag_top_k=0)

    def test_rag_top_k_negative_raises(self):
        with pytest.raises(ValidationError, match="rag_top_k"):
            self._make(rag_top_k=-1)

    def test_rag_semantic_candidates_zero_raises(self):
        with pytest.raises(ValidationError, match="rag_semantic_candidates"):
            self._make(rag_semantic_candidates=0)

    def test_rag_bm25_candidates_zero_raises(self):
        with pytest.raises(ValidationError, match="rag_bm25_candidates"):
            self._make(rag_bm25_candidates=0)

    # --- mmr lambda range ---

    def test_mmr_lambda_below_zero_raises(self):
        with pytest.raises(ValidationError, match="rag_mmr_lambda"):
            self._make(rag_mmr_lambda=-0.1)

    def test_mmr_lambda_above_one_raises(self):
        with pytest.raises(ValidationError, match="rag_mmr_lambda"):
            self._make(rag_mmr_lambda=1.1)

    def test_mmr_lambda_boundary_values_accepted(self):
        assert self._make(rag_mmr_lambda=0.0).rag_mmr_lambda == 0.0
        assert self._make(rag_mmr_lambda=1.0).rag_mmr_lambda == 1.0

    # --- chunk size / overlap ---

    def test_chunk_size_zero_raises(self):
        with pytest.raises(ValidationError, match="rag_chunk_size"):
            self._make(rag_chunk_size=0)

    def test_chunk_overlap_negative_raises(self):
        with pytest.raises(ValidationError, match="rag_chunk_overlap"):
            self._make(rag_chunk_overlap=-1)

    def test_overlap_equal_to_chunk_size_raises(self):
        """overlap == chunk_size makes step=0 → infinite loop in chunk_text."""
        with pytest.raises(ValidationError, match="rag_chunk_overlap"):
            self._make(rag_chunk_size=500, rag_chunk_overlap=500)

    def test_overlap_greater_than_chunk_size_raises(self):
        """overlap > chunk_size makes step negative → infinite loop."""
        with pytest.raises(ValidationError, match="rag_chunk_overlap"):
            self._make(rag_chunk_size=200, rag_chunk_overlap=300)

    def test_valid_overlap_less_than_chunk_size_accepted(self):
        s = self._make(rag_chunk_size=800, rag_chunk_overlap=80)
        assert s.rag_chunk_overlap < s.rag_chunk_size
