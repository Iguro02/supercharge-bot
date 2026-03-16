"""
rag_pipeline.py
Builds and queries the SuperCharge SG knowledge base using ChromaDB + sentence-transformers.
Model is loaded ONCE at startup to avoid per-message reload delay.
"""
from __future__ import annotations

import os
import logging
from pathlib import Path
from typing import Optional

import chromadb
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

KB_PATH     = Path(__file__).parent.parent / "data" / "knowledge_base.txt"
CHROMA_PATH = Path(__file__).parent.parent / "chroma_db"
COLLECTION  = "supercharge_kb"
EMBED_MODEL = "all-MiniLM-L6-v2"
TOP_K       = 3
CHUNK_SIZE  = 400
CHUNK_OVERLAP = 50

# ── Loaded once at startup ────────────────────────────────────────────────────
_embedder: Optional[SentenceTransformer] = None
_collection: Optional[chromadb.Collection] = None

def _get_embedder() -> SentenceTransformer:
    global _embedder
    if _embedder is None:
        logger.info("Loading sentence-transformer model ...")
        _embedder = SentenceTransformer(EMBED_MODEL)
        logger.info("Sentence-transformer model loaded.")
    return _embedder

def _get_collection() -> chromadb.Collection:
    global _collection
    if _collection is not None:
        return _collection
    CHROMA_PATH.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    names = [c.name for c in client.list_collections()]
    if COLLECTION in names:
        col = client.get_collection(COLLECTION)
        if col.count() > 0:
            _collection = col
            return _collection
    _collection = _build_collection(client)
    return _collection

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

def _build_collection(client: chromadb.ClientAPI) -> chromadb.Collection:
    try:
        client.delete_collection(COLLECTION)
    except Exception:
        pass
    col = client.create_collection(COLLECTION)
    embedder = _get_embedder()
    raw = KB_PATH.read_text(encoding="utf-8")
    chunks = _split_text(raw)
    logger.info(f"Embedding {len(chunks)} chunks ...")
    embeddings = embedder.encode(chunks, show_progress_bar=False).tolist()
    col.add(
        documents=chunks,
        embeddings=embeddings,
        ids=[str(i) for i in range(len(chunks))],
        metadatas=[{"idx": i} for i in range(len(chunks))],
    )
    logger.info(f"KB built: {len(chunks)} chunks stored.")
    return col

def build_kb(force_rebuild: bool = False) -> None:
    """Pre-load embedder and collection into memory at startup."""
    global _collection
    if force_rebuild:
        _collection = None
    _get_embedder()
    _get_collection()
    logger.info("Knowledge base ready.")

def retrieve_context(query: str, top_k: int = TOP_K) -> str:
    """Return top-k relevant chunks as a single context string."""
    embedder = _get_embedder()
    col = _get_collection()
    qemb = embedder.encode([query]).tolist()
    results = col.query(query_embeddings=qemb, n_results=top_k)
    docs = results["documents"][0] if results["documents"] else []
    return "\n\n---\n\n".join(docs)