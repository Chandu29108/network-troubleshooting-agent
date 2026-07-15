"""
Ingestion pipeline: file -> text -> chunks -> embeddings -> Chroma.

Why local embeddings (sentence-transformers) instead of an API embedding
model: embeddings are computed for every chunk of every uploaded doc, which
is high-volume compared to LLM calls. Running them locally means uploading
documents never touches your Gemini free-tier quota and never costs money,
no matter how many docs you ingest.
"""
from pathlib import Path

from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.config import get_settings
from app.core.logging_config import logger

settings = get_settings()

_embeddings = None


def get_embeddings() -> HuggingFaceEmbeddings:
    """Lazily load the embedding model once (it's a ~90MB download on first run)."""
    global _embeddings
    if _embeddings is None:
        logger.info("Loading local embedding model: %s", settings.embedding_model_name)
        _embeddings = HuggingFaceEmbeddings(model_name=settings.embedding_model_name)
    return _embeddings


def get_vectorstore() -> Chroma:
    return Chroma(
        collection_name="network_kb",
        embedding_function=get_embeddings(),
        persist_directory=settings.chroma_persist_dir,
    )


def _load_document(path: Path):
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return PyPDFLoader(str(path)).load()
    # .txt, .md, .log and anything else plain-text
    return TextLoader(str(path), encoding="utf-8").load()


def ingest_file(path: Path) -> int:
    """
    Loads a file, splits it into overlapping chunks, embeds them, and stores
    them in the persistent Chroma collection. Returns the number of chunks
    indexed.

    Chunk overlap (150 chars) preserves context across chunk boundaries so a
    fix described across two chunks isn't lost when only one chunk is
    retrieved.
    """
    docs = _load_document(path)
    for doc in docs:
        doc.metadata["source"] = path.name

    splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=150)
    chunks = splitter.split_documents(docs)

    if not chunks:
        return 0

    vectorstore = get_vectorstore()
    vectorstore.add_documents(chunks)
    logger.info("Indexed %d chunks from %s", len(chunks), path.name)
    return len(chunks)
