"""
Thin retrieval wrapper. Kept separate from ingest.py so agent nodes only
import what they need (retrieval), not the heavier ingestion dependencies.
"""
from app.rag.ingest import get_vectorstore


def retrieve_relevant_docs(query: str, k: int = 4) -> list[dict]:
    """
    Returns a list of {"source": ..., "content": ...} dicts for the top-k
    most relevant chunks. Returning source filenames alongside content is
    what lets the synthesis agent produce citations instead of an
    unattributed answer.
    """
    vectorstore = get_vectorstore()
    results = vectorstore.similarity_search(query, k=k)
    return [
        {"source": doc.metadata.get("source", "unknown"), "content": doc.page_content}
        for doc in results
    ]
