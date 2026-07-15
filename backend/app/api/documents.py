"""
Document upload endpoint. Accepts PDF/TXT/MD/LOG files (e.g. vendor
troubleshooting guides, internal runbooks) and indexes them into the Chroma
knowledge base used by retrieval_node, so future diagnoses can cite them.
"""
import tempfile
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, HTTPException

from app.core.logging_config import logger
from app.models.schemas import DocumentUploadResponse
from app.rag.ingest import ingest_file

router = APIRouter(prefix="/api/documents", tags=["documents"])

ALLOWED_SUFFIXES = {".pdf", ".txt", ".md", ".log"}
MAX_FILE_SIZE_MB = 15


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(file: UploadFile = File(...)):
    suffix = Path(file.filename).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{suffix}'. Allowed: {sorted(ALLOWED_SUFFIXES)}",
        )

    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE_MB * 1024 * 1024:
        raise HTTPException(status_code=400, detail=f"File exceeds {MAX_FILE_SIZE_MB}MB limit.")

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(contents)
        tmp_path = Path(tmp.name)

    try:
        # Rename so the stored source filename in Chroma metadata matches
        # the original upload name, not a random tempfile name.
        renamed = tmp_path.with_name(file.filename)
        tmp_path.rename(renamed)
        chunks_indexed = ingest_file(renamed)
    finally:
        try:
            renamed.unlink(missing_ok=True)
        except NameError:
            tmp_path.unlink(missing_ok=True)

    if chunks_indexed == 0:
        logger.warning("No content extracted from %s", file.filename)

    return DocumentUploadResponse(
        filename=file.filename,
        chunks_indexed=chunks_indexed,
        message=f"Indexed {chunks_indexed} chunks into the knowledge base.",
    )
