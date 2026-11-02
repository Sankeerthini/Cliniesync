"""Vector store abstraction for unstructured data (notes, reports, summaries).

Backends
--------
* ``chroma``  - ChromaDB (open-source, embedded, persistent). Default embeddings:
                Chroma's local ONNX all-MiniLM-L6-v2 (no GPU, no torch). Set
                EMBEDDING_MODEL=BAAI/bge-small-en-v1.5 (needs sentence-transformers)
                for a stronger model.
* ``tfidf``   - scikit-learn TF-IDF, in memory. Zero downloads; used as the
                automatic fallback so the demo never breaks offline.

Production alternative: pgvector inside the same PostgreSQL instance.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache

from common.settings import get_settings

log = logging.getLogger("cliniesync.vector")
COLLECTION = "cliniesync_documents"


@dataclass
class Hit:
    id: str
    text: str
    metadata: dict
    score: float  # higher = more similar (0..1)


def _match(meta: dict, where: dict | None) -> bool:
    return not where or all(meta.get(k) == v for k, v in where.items())


class TfidfStore:
    name = "tfidf"

    def __init__(self):
        self.ids: list[str] = []
        self.texts: list[str] = []
        self.metas: list[dict] = []
        self._vec = None
        self._mat = None

    def reset(self) -> None:
        self.__init__()

    def add(self, ids, texts, metadatas) -> None:
        self.ids += list(ids)
        self.texts += list(texts)
        self.metas += list(metadatas)
        self._vec = None

    def _fit(self):
        from sklearn.feature_extraction.text import TfidfVectorizer

        self._vec = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, min_df=1)
        self._mat = self._vec.fit_transform(self.texts) if self.texts else None

    def count(self) -> int:
        return len(self.ids)

    def query(self, text: str, k: int = 6, where: dict | None = None) -> list[Hit]:
        if not self.texts:
            return []
        if self._vec is None:
            self._fit()
        idx = [i for i, m in enumerate(self.metas) if _match(m, where)]
        if not idx:
            return []
        q = self._vec.transform([text])
        sims = (self._mat[idx] @ q.T).toarray().ravel()
        order = sims.argsort()[::-1][:k]
        return [Hit(self.ids[idx[i]], self.texts[idx[i]], self.metas[idx[i]], float(sims[i])) for i in order]


class ChromaStore:
    name = "chroma"

    def __init__(self, path: str, embedding_model: str = "default"):
        import chromadb

        self.client = chromadb.PersistentClient(path=path)
        self.ef = None
        if embedding_model and embedding_model != "default":
            from chromadb.utils import embedding_functions

            self.ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=embedding_model)
        self.embedding_model = embedding_model if self.ef else "all-MiniLM-L6-v2 (ONNX)"
        self._col = self._collection()

    def _collection(self):
        kw = {"name": COLLECTION, "metadata": {"hnsw:space": "cosine"}}
        if self.ef:
            kw["embedding_function"] = self.ef
        return self.client.get_or_create_collection(**kw)

    def reset(self) -> None:
        try:
            self.client.delete_collection(COLLECTION)
        except Exception:
            pass
        self._col = self._collection()

    def add(self, ids, texts, metadatas) -> None:
        ids, texts, metadatas = list(ids), list(texts), list(metadatas)
        clean = [{k: ("" if v is None else v) for k, v in m.items()} for m in metadatas]
        for i in range(0, len(ids), 256):
            self._col.add(ids=ids[i:i + 256], documents=texts[i:i + 256], metadatas=clean[i:i + 256])

    def count(self) -> int:
        return self._col.count()

    def query(self, text: str, k: int = 6, where: dict | None = None) -> list[Hit]:
        kw = {"query_texts": [text], "n_results": k}
        if where:
            kw["where"] = where if len(where) == 1 else {"$and": [{a: b} for a, b in where.items()]}
        res = self._col.query(**kw)
        hits = []
        for i, doc_id in enumerate(res["ids"][0]):
            hits.append(Hit(doc_id, res["documents"][0][i], res["metadatas"][0][i],
                            1 - float(res["distances"][0][i])))
        return hits


@lru_cache
def get_vector_store():
    """Pick the backend once per process (VECTOR_BACKEND=auto|chroma|tfidf)."""
    s = get_settings()
    if s.vector_backend in ("auto", "chroma"):
        try:
            store = ChromaStore(str(s.vector_dir), s.embedding_model)
            store.query("warm-up", k=1)  # triggers embedding-model load / download
            return store
        except Exception as exc:  # pragma: no cover - environment dependent
            if s.vector_backend == "chroma":
                raise
            log.warning("ChromaDB unavailable (%s) - falling back to TF-IDF", exc)
    store = TfidfStore()
    _hydrate_tfidf(store)
    return store


def _hydrate_tfidf(store: TfidfStore) -> None:
    """The TF-IDF store lives in memory: rebuild it from the documents table."""
    from ai.rag.indexer import document_chunks

    try:
        ids, texts, metas = document_chunks()
        store.add(ids, texts, metas)
    except Exception as exc:  # DB not ready yet
        log.info("TF-IDF store empty: %s", exc)
