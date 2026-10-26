"""A dependency-free Okapi BM25 implementation.

The corpus here is small (hundreds of chunks), so an in-memory inverted index
rebuilt at startup is both simpler and faster than a database round-trip.
"""

from __future__ import annotations

import math
import re
from collections import Counter

_TOKEN_RE = re.compile(r"[a-z0-9']+")

STOPWORDS = frozenset(
    [
        "a",
        "about",
        "above",
        "after",
        "again",
        "against",
        "all",
        "am",
        "an",
        "and",
        "any",
        "are",
        "aren't",
        "as",
        "at",
        "be",
        "because",
        "been",
        "before",
        "being",
        "below",
        "between",
        "both",
        "but",
        "by",
        "can",
        "cannot",
        "could",
        "couldn't",
        "did",
        "didn't",
        "do",
        "does",
        "doesn't",
        "doing",
        "don't",
        "down",
        "during",
        "each",
        "few",
        "for",
        "from",
        "further",
        "had",
        "hadn't",
        "has",
        "hasn't",
        "have",
        "haven't",
        "having",
        "he",
        "her",
        "here",
        "hers",
        "herself",
        "him",
        "himself",
        "his",
        "how",
        "i",
        "i'm",
        "if",
        "in",
        "into",
        "is",
        "isn't",
        "it",
        "it's",
        "its",
        "itself",
        "just",
        "me",
        "more",
        "most",
        "my",
        "myself",
        "no",
        "nor",
        "not",
        "of",
        "off",
        "on",
        "once",
        "only",
        "or",
        "other",
        "ought",
        "our",
        "ours",
        "ourselves",
        "out",
        "over",
        "own",
        "same",
        "shan't",
        "she",
        "should",
        "shouldn't",
        "so",
        "some",
        "such",
        "than",
        "that",
        "the",
        "their",
        "theirs",
        "them",
        "themselves",
        "then",
        "there",
        "these",
        "they",
        "this",
        "those",
        "through",
        "to",
        "too",
        "under",
        "until",
        "up",
        "very",
        "was",
        "wasn't",
        "we",
        "were",
        "weren't",
        "what",
        "when",
        "where",
        "which",
        "while",
        "who",
        "whom",
        "why",
        "will",
        "with",
        "won't",
        "would",
        "wouldn't",
        "you",
        "your",
        "yours",
        "yourself",
        "yourselves",
        "also",
        "may",
        "might",
        "must",
        "need",
        "needs",
        "needed",
        "feel",
        "feels",
        "feeling",
        "get",
        "gets",
        "got",
        "really",
        "lot",
        "lots",
        "bit",
        "kind",
        "sort",
        "always",
        "usually",
        "sometimes",
        "much",
        "many",
        "going",
        "goes",
        "go",
    ]
)


def tokenize(text: str) -> list[str]:
    """Lowercase tokenisation with a light stemming pass and stopword removal."""

    tokens: list[str] = []
    for raw in _TOKEN_RE.findall(text.lower()):
        if raw in STOPWORDS or len(raw) < 2:
            continue
        tokens.append(_stem(raw))
    return tokens


def _stem(token: str) -> str:
    if len(token) > 4 and token.endswith("ies"):
        return token[:-3] + "y"
    if len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
        return token[:-1]
    return token


class BM25Index:
    """Okapi BM25 (k1=1.5, b=0.75) over a fixed list of documents."""

    def __init__(self, documents: list[list[str]], k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self.doc_tokens = documents
        self.doc_len = [len(doc) for doc in documents]
        self.avg_len = (sum(self.doc_len) / len(documents)) if documents else 0.0
        self.term_freqs: list[Counter[str]] = [Counter(doc) for doc in documents]
        self.df: Counter[str] = Counter()
        for doc in documents:
            self.df.update(set(doc))
        self.n_docs = len(documents)

    def _idf(self, term: str) -> float:
        df = self.df.get(term, 0)
        return math.log(1 + (self.n_docs - df + 0.5) / (df + 0.5))

    def idf(self, term: str) -> float:
        return self._idf(term)

    def coverage(self, query_tokens: list[str], doc_index: int) -> float:
        """Share of the query's IDF mass that this document actually contains.

        A document that matches one incidental word out of five scores low, which is
        what keeps out-of-domain questions from looking relevant.
        """

        return self.concept_coverage([[token] for token in query_tokens], doc_index)

    def concept_coverage(self, groups: list[tuple[str, ...]], doc_index: int) -> float:
        """IDF-weighted share of concept groups satisfied by a document.

        The group's weight comes from its most common variant in the corpus, so a
        synonym never inflates the weight of a concept it happens to represent.
        """

        if not self.n_docs or doc_index >= self.n_docs or not groups:
            return 0.0
        freqs = self.term_freqs[doc_index]
        total = 0.0
        matched = 0.0
        for group in groups:
            if not group:
                continue
            anchor = max(group, key=lambda term: self.df.get(term, 0))
            weight = self._idf(anchor)
            total += weight
            if any(freqs.get(term, 0) > 0 for term in group):
                matched += weight
        return matched / total if total else 0.0

    def scores(self, query_tokens: list[str]) -> list[float]:
        if not self.n_docs or not query_tokens:
            return [0.0] * self.n_docs
        unique_terms = list(dict.fromkeys(query_tokens))
        out = []
        for index, freqs in enumerate(self.term_freqs):
            length = self.doc_len[index] or 1
            norm = self.k1 * (1 - self.b + self.b * length / (self.avg_len or 1))
            score = 0.0
            for term in unique_terms:
                freq = freqs.get(term, 0)
                if not freq:
                    continue
                score += self._idf(term) * (freq * (self.k1 + 1)) / (freq + norm)
            out.append(score)
        return out

    def search(self, query: str | list[str], limit: int = 5) -> list[tuple[int, float]]:
        tokens = tokenize(query) if isinstance(query, str) else query
        scored = self.scores(tokens)
        ranked = sorted(range(len(scored)), key=lambda i: scored[i], reverse=True)
        return [(i, round(scored[i], 6)) for i in ranked[:limit] if scored[i] > 0]
