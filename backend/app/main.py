"""
FastAPI application entrypoint.
Run with: uvicorn app.main:app --reload
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import chat, documents
from app.config import get_settings
from app.core.logging_config import logger
from app.db.database import init_db

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up: initializing database tables")
    await init_db()
    yield
    logger.info("Shutting down")


app = FastAPI(
    title="AI Network Troubleshooting Agent",
    description="Multi-agent (LangGraph) assistant that diagnoses network "
    "issues from logs/symptoms, retrieves relevant docs (RAG), and "
    "suggests fixes with CLI commands.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router)
app.include_router(documents.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
