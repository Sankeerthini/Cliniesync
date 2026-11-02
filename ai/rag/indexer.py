"""Chunk documents from the unified layer and (re)build the vector index."""
from __future__ import annotations

from sqlalchemy import select

from database.models import Document
from database.session import session_scope

MAX_CHARS = 900
OVERLAP = 150


def chunk_text(text: str) -> list[str]:
    """Paragraph-aware chunking; most clinic notes fit in a single chunk."""
    text = text.strip()
    if len(text) <= MAX_CHARS:
        return [text]
    chunks, cur = [], ""
    for para in text.split("\n"):
        if len(cur) + len(para) + 1 > MAX_CHARS and cur:
            chunks.append(cur)
            cur = cur[-OVERLAP:]
        cur = (cur + "\n" + para).strip()
    if cur:
        chunks.append(cur)
    return chunks


def document_chunks() -> tuple[list[str], list[str], list[dict]]:
    ids, texts, metas = [], [], []
    with session_scope() as s:
        for d in s.scalars(select(Document)):
            for i, ch in enumerate(chunk_text(d.text)):
                ids.append(f"{d.doc_id}#{i}")
                texts.append(ch)
                metas.append({"doc_id": d.doc_id, "patient_id": d.patient_id, "child_id": d.child_id or "",
                              "visit_id": d.visit_id or "", "doc_type": d.doc_type, "title": d.title,
                              "doc_date": d.doc_date.isoformat(), "source_system": d.source_system})
    return ids, texts, metas


def rebuild_index() -> dict:
    from ai.rag.vector_store import get_vector_store

    store = get_vector_store()
    store.reset()
    ids, texts, metas = document_chunks()
    store.add(ids, texts, metas)
    return {"backend": store.name, "chunks_indexed": len(ids),
            "embedding_model": getattr(store, "embedding_model", "tf-idf (word 1-2 grams)")}
