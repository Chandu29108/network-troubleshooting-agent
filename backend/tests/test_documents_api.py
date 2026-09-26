"""
API tests for /api/documents/upload — covers validation paths only (file
type, size limit). The actual ingestion path (embedding model + Chroma) is
intentionally not exercised here: it's slow, downloads a model on first
run, and is better covered by a separate integration test run manually or
in a slower CI job than the default fast unit/API suite.
"""
import pytest


@pytest.mark.asyncio
async def test_rejects_unsupported_file_type(client):
    files = {"file": ("malware.exe", b"not really a virus", "application/octet-stream")}
    response = await client.post("/api/documents/upload", files=files)
    assert response.status_code == 400
    assert "Unsupported file type" in response.json()["detail"]


@pytest.mark.asyncio
async def test_rejects_oversized_file(client):
    # MAX_FILE_SIZE_MB is 15; send one byte over that as a .txt file.
    oversized = b"x" * (15 * 1024 * 1024 + 1)
    files = {"file": ("big.txt", oversized, "text/plain")}
    response = await client.post("/api/documents/upload", files=files)
    assert response.status_code == 400
    assert "exceeds" in response.json()["detail"]
