"""
rag_pipeline.py
Builds and queries the SuperCharge SG knowledge base using ChromaDB + sentence-transformers.
"""
from __future__ import annotations

import os
import logging
from pathlib import Path
from typing import Optional

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

# ── constants ────────────────────────────────────────────────────────────────
KB_PATH       = Path(__file__).parent.parent / "data" / "knowledge_base.txt"
CHROMA_PATH   = Path(__file__).parent.parent / "chroma_db"
COLLECTION    = "supercharge_kb"
EMBED_MODEL   = "all-MiniLM-L6-v2"
TOP_K         = 3
CHUNK_SIZE    = 400   # target tokens per chunk
CHUNK_OVERLAP = 50

# ── embedder (loaded once) ───────────────────────────────────────────────────
_embedder: Optional[SentenceTransformer] = None

def _get_embedder() -> SentenceTransformer:
    global _embedder
    if _embedder is None:
        logger.info("Loading sentence-transformer model …")
        _embedder = SentenceTransformer(EMBED_MODEL)
    return _embedder

# ── text splitter (simple, no dependency on langchain) ───────────────────────
def _split_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split on double-newlines (logical sections) then by char length."""
    sections = [s.strip() for s in text.split("\n\n") if s.strip()]
    chunks: list[str] = []
    for section in sections:
        words = section.split()
        if len(words) <= chunk_size:
            chunks.append(section)
        else:
            # slide a window
            step = chunk_size - overlap
            for i in range(0, len(words), step):
                chunk = " ".join(words[i : i + chunk_size])
                if chunk:
                    chunks.append(chunk)
    return chunks

# ── build / load collection ──────────────────────────────────────────────────
def build_kb(force_rebuild: bool = False) -> chromadb.Collection:
    """Build the vector store from the knowledge base text file.
    If already built and force_rebuild=False, just returns the existing collection.
    """
    CHROMA_PATH.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(CHROMA_PATH))

    if COLLECTION in [c.name for c in client.list_collections()]:
        col = client.get_collection(COLLECTION)
        if col.count() > 0 and not force_rebuild:
            logger.info(f"KB already built: {col.count()} chunks loaded.")
            return col
        client.delete_collection(COLLECTION)

    col = client.create_collection(COLLECTION)
    embedder = _get_embedder()

    raw = KB_PATH.read_text(encoding="utf-8")
    chunks = _split_text(raw)
    logger.info(f"Embedding {len(chunks)} chunks …")

    embeddings = embedder.encode(chunks, show_progress_bar=False).tolist()
    col.add(
        documents=chunks,
        embeddings=embeddings,
        ids=[str(i) for i in range(len(chunks))],
        metadatas=[{"idx": i} for i in range(len(chunks))],
    )
    logger.info(f"KB built: {len(chunks)} chunks stored.")
    return col

# ── query ────────────────────────────────────────────────────────────────────
def retrieve_context(query: str, top_k: int = TOP_K) -> str:
    """Return top-k relevant chunks concatenated as a single context string."""
    CHROMA_PATH.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(CHROMA_PATH))

    try:
        col = client.get_collection(COLLECTION)
    except Exception:
        col = build_kb()

    embedder = _get_embedder()
    qemb = embedder.encode([query]).tolist()
    results = col.query(query_embeddings=qemb, n_results=top_k)
    docs = results["documents"][0] if results["documents"] else []
    return "\n\n---\n\n".join(docs)
