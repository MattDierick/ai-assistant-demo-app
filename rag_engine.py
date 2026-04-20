"""
Lightweight RAG engine – loads TXT files, chunks them, embeds with
sentence-transformers and stores vectors in a FAISS index for fast retrieval.
"""

import os
import uuid
import numpy as np

# Lazy-loaded heavy dependencies
_model = None
_faiss = None


def _get_model():
    """Lazy-load the sentence-transformer model (downloaded once)."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def _get_faiss():
    """Lazy-import faiss."""
    global _faiss
    if _faiss is None:
        import faiss as _f
        _faiss = _f
    return _faiss


# ---------------------------------------------------------------------------
# In-memory document store
# ---------------------------------------------------------------------------
# _chunks: list of dicts  { id, doc_id, doc_name, text }
# _index:  faiss.IndexFlatIP  (inner-product on L2-normalised vectors ≈ cosine)


_chunks: list[dict] = []
_index = None
_documents: dict[str, dict] = {}  # doc_id -> { name, chunk_count }

CHUNK_SIZE = 500       # characters per chunk
CHUNK_OVERLAP = 50     # overlap between consecutive chunks


def _chunk_text(text: str) -> list[str]:
    """Split text into overlapping chunks."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + CHUNK_SIZE
        chunks.append(text[start:end])
        start += CHUNK_SIZE - CHUNK_OVERLAP
    return [c.strip() for c in chunks if c.strip()]


def _rebuild_index():
    """Rebuild the FAISS index from current chunks."""
    global _index
    faiss = _get_faiss()
    model = _get_model()

    if not _chunks:
        _index = None
        return

    texts = [c["text"] for c in _chunks]
    embeddings = model.encode(texts, normalize_embeddings=True).astype("float32")
    dim = embeddings.shape[1]
    _index = faiss.IndexFlatIP(dim)
    _index.add(embeddings)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def add_document(filename: str, text: str) -> str:
    """Add a TXT document to the knowledge base. Returns the doc_id."""
    doc_id = uuid.uuid4().hex[:12]
    parts = _chunk_text(text)

    for part in parts:
        _chunks.append({
            "id": uuid.uuid4().hex,
            "doc_id": doc_id,
            "doc_name": filename,
            "text": part,
        })

    _documents[doc_id] = {"name": filename, "chunk_count": len(parts)}
    _rebuild_index()
    return doc_id


def remove_document(doc_id: str) -> bool:
    """Remove a document and its chunks from the knowledge base."""
    global _chunks
    if doc_id not in _documents:
        return False
    _chunks = [c for c in _chunks if c["doc_id"] != doc_id]
    del _documents[doc_id]
    _rebuild_index()
    return True


def list_documents() -> list[dict]:
    """Return a list of loaded documents."""
    return [
        {"id": doc_id, "name": info["name"], "chunk_count": info["chunk_count"]}
        for doc_id, info in _documents.items()
    ]


def retrieve(query: str, top_k: int = 3) -> list[dict]:
    """Retrieve the top-k most relevant chunks for a query."""
    if _index is None or not _chunks:
        return []

    model = _get_model()
    q_emb = model.encode([query], normalize_embeddings=True).astype("float32")
    scores, indices = _index.search(q_emb, min(top_k, len(_chunks)))

    results = []
    for score, idx in zip(scores[0], indices[0]):
        if idx < 0:
            continue
        chunk = _chunks[idx]
        results.append({
            "doc_name": chunk["doc_name"],
            "text": chunk["text"],
            "score": float(score),
        })
    return results


def load_default_document(filepath: str) -> str | None:
    """Load a default document from disk if it exists and is not already loaded.
    Returns the doc_id if loaded, or None if the file doesn't exist or is already loaded.
    """
    if not os.path.isfile(filepath):
        return None

    filename = os.path.basename(filepath)

    # Check if already loaded (avoid duplicates on restart)
    for info in _documents.values():
        if info["name"] == filename:
            return None

    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()

    if not text.strip():
        return None

    return add_document(filename, text)


def build_rag_context(query: str, top_k: int = 3) -> str:
    """Return a formatted context block to prepend to the LLM prompt."""
    hits = retrieve(query, top_k)
    if not hits:
        return ""

    parts = ["Here is relevant context from the knowledge base:\n"]
    for i, hit in enumerate(hits, 1):
        parts.append(f"[{i}] (from {hit['doc_name']}, relevance {hit['score']:.2f})")
        parts.append(hit["text"])
        parts.append("")

    parts.append("Use the context above to answer the user's question.\n")
    return "\n".join(parts)
