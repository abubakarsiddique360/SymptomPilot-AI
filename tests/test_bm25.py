from __future__ import annotations

from symptompilot.retrieval.bm25 import BM25Index, tokenize


def test_tokenize_drops_stopwords_and_stems_plurals() -> None:
    tokens = tokenize("The patients have chest pains and a fever")
    assert "chest" in tokens
    assert "pain" in tokens
    assert "fever" in tokens
    assert "the" not in tokens
    assert "have" not in tokens


def test_bm25_ranks_matching_document_first() -> None:
    index = BM25Index(
        [
            tokenize("sudden chest pain with sweating"),
            tokenize("sore throat and runny nose"),
            tokenize("lower back ache after lifting"),
        ]
    )
    ranked = index.search("chest pain", limit=3)
    assert ranked
    assert ranked[0][0] == 0
    assert ranked[0][1] > 0


def test_bm25_returns_nothing_for_unrelated_query() -> None:
    index = BM25Index([tokenize("sore throat and runny nose")])
    assert index.search("quantum chromodynamics", limit=3) == []


def test_bm25_handles_empty_corpus() -> None:
    index = BM25Index([])
    assert index.search("chest pain") == []


def test_rare_terms_outweigh_common_terms() -> None:
    index = BM25Index(
        [
            tokenize("pain pain pain pain pain"),
            tokenize("pain with thunderclap headache"),
        ]
    )
    ranked = index.search("thunderclap", limit=2)
    assert ranked and ranked[0][0] == 1
