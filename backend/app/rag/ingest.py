"""
Ingestion pipeline: file -> text -> chunks -> embeddings -> Chroma.

Uses Gemini's embedding API instead of a local sentence-transformers model.
The local model's transitive PyTorch dependency pushed the backend's memory
footprint well past Render's free-tier 512MB cap -- import alone (before
serving a single request) was enough to OOM the container. Calling the
Gemini API for embeddings instead removes PyTorch from the dependency tree
entirely. The trade-off: embedding calls now count against the same
GOOGLE_API_KEY quota as chat completions, but embeddings are cheap and the
free tier's quota comfortably covers a portfolio-scale amount of document
uploads.
"""
from pathlib import Path

from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_community.vectorstores import Chroma
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.config import get_settings
from app.core.logging_config import logger

settings = get_settings()

_embeddings = None


def get_embeddings() -> GoogleGenerativeAIEmbeddings:
    """Lazily create the embeddings client once (a thin API wrapper, no local model to load)."""
    global _embeddings
    if _embeddings is None:
        logger.info("Using Gemini embedding model: %s", settings.embedding_model_name)
        _embeddings = GoogleGenerativeAIEmbeddings(
            model=settings.embedding_model_name,
            google_api_key=settings.google_api_key,
        )
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
