"""
rag_pipeline.py
Pure Python RAG — no ChromaDB, no dependency conflicts.
Uses paraphrase-MiniLM-L3-v2 (fast, CPU-friendly) for embeddings.
Query embeddings are cached to avoid re-encoding identical queries.
Falls back to live SuperCharge website fetch when KB confidence is low.
"""
from __future__ import annotations

import logging
import math
from pathlib import Path
from typing import Optional
from functools import lru_cache

from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

KB_PATH       = Path(__file__).parent.parent / "data" / "knowledge_base.txt"
EMBED_MODEL   = "paraphrase-MiniLM-L3-v2"   # 3x faster than L6, ~17MB vs ~90MB
TOP_K         = 3
CHUNK_SIZE    = 400
CHUNK_OVERLAP = 50
CONFIDENCE_THRESHOLD = 0.30

# ── In-memory store ───────────────────────────────────────────────────────────
_embedder:   Optional[SentenceTransformer] = None
_chunks:     list[str]         = []
_embeddings: list[list[float]] = []


def _get_embedder() -> SentenceTransformer:
    global _embedder
    if _embedder is None:
        logger.info("Loading sentence-transformer model ...")
        _embedder = SentenceTransformer(EMBED_MODEL)
        logger.info("Model loaded.")
    return _embedder


def _split_text(text: str) -> list[str]:
    sections = [s.strip() for s in text.split("\n\n") if s.strip()]
    chunks: list[str] = []
    for section in sections:
        words = section.split()
        if len(words) <= CHUNK_SIZE:
            chunks.append(section)
        else:
            step = CHUNK_SIZE - CHUNK_OVERLAP
            for i in range(0, len(words), step):
                chunk = " ".join(words[i : i + CHUNK_SIZE])
                if chunk:
                    chunks.append(chunk)
    return chunks


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot   = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(x * x for x in b))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


def build_kb(force_rebuild: bool = False) -> None:
    """Pre-load embedder and embed all KB chunks at startup."""
    global _chunks, _embeddings
    if _chunks and not force_rebuild:
        logger.info(f"KB already loaded: {len(_chunks)} chunks.")
        return
    embedder    = _get_embedder()
    raw         = KB_PATH.read_text(encoding="utf-8")
    _chunks     = _split_text(raw)
    logger.info(f"Embedding {len(_chunks)} chunks ...")
    _embeddings = embedder.encode(
        _chunks,
        show_progress_bar=False,
        batch_size=64,        # process in batches for speed
        normalize_embeddings=True,  # pre-normalize for faster cosine
    ).tolist()
    logger.info(f"KB ready: {len(_chunks)} chunks in memory.")


@lru_cache(maxsize=256)
def _encode_query(query: str) -> tuple:
    """Encode a query string — cached so identical queries skip re-encoding."""
    embedder = _get_embedder()
    emb = embedder.encode(
        [query],
        show_progress_bar=False,
        normalize_embeddings=True,
    ).tolist()[0]
    return tuple(emb)  # tuple is hashable for lru_cache


def retrieve_context(query: str, top_k: int = TOP_K) -> str:
    """
    Retrieve top-k chunks from KB by cosine similarity.
    If best score < CONFIDENCE_THRESHOLD, supplement with live web fetch.
    """
    if not _chunks:
        build_kb()

    query_emb = list(_encode_query(query))  # cached
    scores    = [_cosine_similarity(query_emb, emb) for emb in _embeddings]
    top_idx   = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
    top_scores = [scores[i] for i in top_idx]
    top_docs   = [_chunks[i] for i in top_idx]

    best_score = top_scores[0] if top_scores else 0.0
    logger.info(f"RAG best score: {best_score:.3f} (threshold: {CONFIDENCE_THRESHOLD})")

    kb_context = "\n\n---\n\n".join(top_docs)

    # ── Supplement with live web fetch if confidence is low ───────────────────
    if best_score < CONFIDENCE_THRESHOLD:
        logger.info("Low confidence — fetching live content from SuperCharge website ...")
        try:
            from src.web_fetcher import fetch_supercharge_context
            web_context = fetch_supercharge_context(query)
            if web_context:
                logger.info("Web content fetched — supplementing KB context.")
                return (
                    f"[Knowledge Base]\n{kb_context}\n\n"
                    f"[Live Website Content]\n{web_context}"
                )
        except Exception as e:
            logger.warning(f"Web fetch failed: {e} — using KB only.")

    return kb_context
