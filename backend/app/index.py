"""Hybrid retrieval index: BM25 (keyword) + dense embeddings, combined with
Reciprocal Rank Fusion (RRF).

Usage:
    from .index import INDEX
    INDEX.build()          # call after any new doc goes live
    hits = INDEX.search("वय किती असावी?", k=6)

The index is an in-process singleton.  Embeddings are cached in the DB so that
a rebuild only calls the encoder for new (un-embedded) chunks.
"""
from __future__ import annotations

import asyncio
import sqlite3

import numpy as np
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer

from . import db
from .config import EMBED_MODEL
from .textutil import tokens

# ---------------------------------------------------------------------------
# Lazy-loaded encoder singleton
# ---------------------------------------------------------------------------

_encoder: SentenceTransformer | None = None


def _get_encoder() -> SentenceTransformer:
    global _encoder
    if _encoder is None:
        _encoder = SentenceTransformer(EMBED_MODEL)
    return _encoder


# ---------------------------------------------------------------------------
# Index class
# ---------------------------------------------------------------------------

_LIVE_CHUNKS_SQL = """
    SELECT c.id, c.text, c.page_no, c.document_id, c.embedding,
           d.gr_number, d.gr_date, d.file_path
    FROM   chunks c
    JOIN   documents d ON d.id = c.document_id
    WHERE  d.status = 'live'
"""


class Index:
    def __init__(self) -> None:
        self.rows:  list[sqlite3.Row] = []
        self.bm25:  BM25Okapi | None  = None
        self.emb:   np.ndarray | None = None   # shape (N, D)

    # ------------------------------------------------------------------
    def build(self) -> None:
        """(Re-)build the in-memory index from all live chunks in the DB.

        Called synchronously (e.g., from asyncio.to_thread).
        """
        self.rows = db.fetchall(_LIVE_CHUNKS_SQL)
        if not self.rows:
            self.bm25 = None
            self.emb  = None
            return

        # BM25 on the full corpus
        self.bm25 = BM25Okapi([tokens(r["text"]) for r in self.rows])

        # Encode chunks that have no cached embedding yet
        missing = [r for r in self.rows if r["embedding"] is None]
        if missing:
            enc = _get_encoder()
            vecs = enc.encode(
                ["passage: " + r["text"] for r in missing],
                normalize_embeddings=True,
                show_progress_bar=False,
            )
            for row, vec in zip(missing, vecs):
                db.execute(
                    "UPDATE chunks SET embedding = ? WHERE id = ?",
                    (vec.astype("float32").tobytes(), row["id"]),
                )
            # Re-fetch so all rows have embeddings
            self.rows = db.fetchall(_LIVE_CHUNKS_SQL)

        # Stack all embeddings into a matrix
        self.emb = np.vstack(
            [np.frombuffer(r["embedding"], dtype="float32") for r in self.rows]
        )

    # ------------------------------------------------------------------
    def search(self, query: str, k: int = 6) -> list[sqlite3.Row]:
        """Return up to k chunks most relevant to `query` via RRF."""
        if not self.rows or self.bm25 is None:
            return []

        # BM25 scores
        bm_scores = self.bm25.get_scores(tokens(query))

        # Dense scores
        enc = _get_encoder()
        qvec = enc.encode(
            ["query: " + query],
            normalize_embeddings=True,
            show_progress_bar=False,
        )[0]
        dense_scores = self.emb @ qvec  # cosine similarity (vecs are normalised)

        # RRF combination
        rrf: dict[int, float] = {}
        for rank, idx in enumerate(np.argsort(-bm_scores)[:20]):
            rrf[int(idx)] = rrf.get(int(idx), 0.0) + 1.0 / (60 + rank)
        for rank, idx in enumerate(np.argsort(-dense_scores)[:20]):
            rrf[int(idx)] = rrf.get(int(idx), 0.0) + 1.0 / (60 + rank)

        top_k = sorted(rrf, key=rrf.__getitem__, reverse=True)[:k]
        return [self.rows[i] for i in top_k]

    # ------------------------------------------------------------------
    async def build_async(self) -> None:
        """Thread-safe async wrapper around build()."""
        await asyncio.to_thread(self.build)


# ---------------------------------------------------------------------------
# Module-level singleton — import this everywhere
# ---------------------------------------------------------------------------

INDEX = Index()
