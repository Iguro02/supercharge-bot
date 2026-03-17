"""
rag_pipeline.py
Pure Python RAG — no ChromaDB, no dependency conflicts.
Uses sentence-transformers for embeddings + cosine similarity search.
Works on any platform with zero version conflicts.
"""
from __future__ import annotations

import logging
import math
from pathlib import Path
from typing import Optional

from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

KB_PATH     = Path(__file__).parent.parent / "data" / "knowledge_base.txt"
EMBED_MODEL = "all-MiniLM-L6-v2"
TOP_K       = 3
CHUNK_SIZE  = 400
CHUNK_OVERLAP = 50

# ── In-memory store ───────────────────────────────────────────────────────────
_embedder:   Optional[SentenceTransformer] = None
_chunks:     list[str]       = []
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
    global _chunks, _embeddings
    if _chunks and not force_rebuild:
        logger.info(f"KB already loaded: {len(_chunks)} chunks.")
        return
    embedder = _get_embedder()
    raw      = KB_PATH.read_text(encoding="utf-8")
    _chunks  = _split_text(raw)
    logger.info(f"Embedding {len(_chunks)} chunks ...")
    _embeddings = embedder.encode(_chunks, show_progress_bar=False).tolist()
    logger.info(f"KB ready: {len(_chunks)} chunks in memory.")

def retrieve_context(query: str, top_k: int = TOP_K) -> str:
    if not _chunks:
        build_kb()
    embedder  = _get_embedder()
    query_emb = embedder.encode([query]).tolist()[0]
    scores    = [_cosine_similarity(query_emb, emb) for emb in _embeddings]
    top_idx   = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
    top_docs  = [_chunks[i] for i in top_idx]
    return "\n\n---\n\n".join(top_docs)