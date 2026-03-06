from __future__ import annotations

import json
from pathlib import Path

from langchain_core.documents import Document
from langchain_core.vectorstores import InMemoryVectorStore

from app.llm import get_embeddings

_store: InMemoryVectorStore | None = None

DATA_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "knowledge_base.json"


def _load_store() -> InMemoryVectorStore:
    global _store
    if _store is not None:
        return _store

    with open(DATA_PATH) as f:
        articles = json.load(f)

    docs = [
        Document(
            page_content=f"{a['title']}\n\n{a['content']}",
            metadata={"id": a["id"], "category": a["category"], "tags": a.get("tags", [])},
        )
        for a in articles
    ]

    _store = InMemoryVectorStore.from_documents(docs, get_embeddings())
    return _store


def retrieve(query: str, k: int = 3) -> list[str]:
    store = _load_store()
    results = store.similarity_search(query, k=k)
    return [doc.page_content for doc in results]
