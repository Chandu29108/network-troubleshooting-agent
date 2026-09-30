"""
FastAPI application entrypoint.
Run with: uvicorn app.main:app --reload
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api import chat, documents
from app.config import get_settings
from app.core.logging_config import logger
from app.core.observability import init_sentry
from app.core.rate_limit import limiter
from app.db.database import init_db

settings = get_settings()

# Before the app is created, so Sentry can catch anything that goes wrong
# during startup too (e.g. a bad DATABASE_URL), not just request-time errors.
init_sentry()


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
    allow_origins=settings.frontend_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.include_router(chat.router)
app.include_router(documents.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
