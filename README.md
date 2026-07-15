# NetAgent — AI Network Troubleshooting Agent

A multi-agent assistant for a telecom NOC: it takes a symptom description or
raw router logs, diagnoses the likely issue (optionally running `ping` /
`traceroute` / a log parser as tools), retrieves relevant internal
documentation (RAG), and streams back a fix with CLI commands and citations.

```
Router logs / symptom
        │
        ▼
   ┌─────────┐      diagnostic path       ┌──────────────┐
   │ Router  │ ──────────────────────────>│  Diagnostic   │──┐
   │ Agent   │                             │  Agent        │  │
   └─────────┘                             │ (tool-calling)│  │
        │  general question path           └──────────────┘  │
        └──────────────────────────────────────────────────> │
                                                               ▼
                                                    ┌────────────────┐
                                                    │ Retrieval Agent │  (RAG / ChromaDB)
                                                    └────────────────┘
                                                               │
                                                               ▼
                                                    ┌────────────────┐
                                                    │ Synthesis Agent │ ──> streamed answer + citations
                                                    └────────────────┘
```

## Why this stack (and why it costs $0)

| Layer | Choice | Reasoning |
|---|---|---|
| LLM | **Gemini 1.5 Flash** | Only one of the three requested LLMs with a genuinely free API tier — no card required. Swappable: see `app/agents/nodes.py::_llm`. |
| Orchestration | **LangGraph** | Models the router → diagnostic → retrieval → synthesis pipeline as an explicit graph with state, not a single mega-prompt — each agent is independently testable/tunable. |
| Vector DB | **ChromaDB** + **local sentence-transformers embeddings** | Embeddings run on CPU locally (no API calls), so uploading documents never touches your Gemini quota or costs anything, however many docs you add. |
| Conversation memory | **SQLite via SQLAlchemy (async)** | Zero setup, file-based. Because access goes through the ORM, switching to Postgres later is a one-line `DATABASE_URL` change, not a rewrite. |
| Streaming | **SSE via `astream_events`** | Streams both agent-stage status ("Diagnosing…") and the final answer token-by-token, so the multi-agent handoff is visible instead of a black-box spinner. |
| Frontend | **Next.js / React** | Portfolio-grade UI with a live "pipeline rail" showing which agent is currently working. |
| Deployment | **Docker Compose** | Runs both services locally for free; same images deploy to Render/Railway free tiers if you want it public (note: free tiers sleep on inactivity). |

## Project structure

```
backend/
  app/
    agents/       # LangGraph nodes, prompts, graph wiring
    tools/        # ping/traceroute + log parser (LangChain @tool)
    rag/          # document ingestion + retrieval (ChromaDB)
    db/           # SQLAlchemy models + async session
    api/          # FastAPI routers (chat, documents)
    core/         # logging
    config.py     # env-based settings
    main.py       # FastAPI app entrypoint
frontend/
  app/            # Next.js App Router pages
  components/     # ChatWindow, PipelineRail, MessageBubble, FileUpload
  lib/api.ts      # SSE client
sample_docs/      # seed knowledge-base doc so RAG works immediately
.github/workflows/ci.yml   # lint + build pipeline
docker-compose.yml
```

## Setup (local, no Docker)

### 1. Get a free Gemini API key
Go to https://aistudio.google.com/apikey — no credit card required.

### 2. Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# edit .env and paste your GOOGLE_API_KEY

uvicorn app.main:app --reload
# API now running at http://localhost:8000
```

### 3. Seed the knowledge base (optional but recommended)
Upload the sample runbook so the RAG step has something to retrieve:
```bash
curl -F "file=@../sample_docs/network_troubleshooting_kb.md" \
  http://localhost:8000/api/documents/upload
```

### 4. Frontend
```bash
cd frontend
npm install
cp .env.local.example .env.local   # defaults already point at localhost:8000
npm run dev
# UI now running at http://localhost:3000
```

Try: *"Interface Gi0/1 keeps flapping every few minutes, high CRC error
count"* — watch the pipeline rail light up through each agent, then check
the citation pill under the answer (it should cite the seeded runbook).

## Setup (Docker)
```bash
cp backend/.env.example backend/.env   # add your GOOGLE_API_KEY
docker compose up --build
```

## API reference (quick)
- `POST /api/chat/stream` — SSE stream of the agent's reasoning + answer. Body: `{"message": "...", "conversation_id": "optional"}`
- `GET /api/chat/conversations/{id}` — full message history for a conversation
- `POST /api/documents/upload` — multipart file upload (`.pdf`, `.txt`, `.md`, `.log`) to index into the knowledge base
- `GET /health` — liveness check

## What's implemented vs. deferred
Implemented: multi-agent LangGraph workflow, tool calling (ping/traceroute/log
parser), RAG with citations, streaming responses, conversation memory,
document upload, structured logging, Dockerized deployment, CI pipeline.

Deliberately deferred (not selected for v1, but the architecture leaves room
for them): user authentication (would slot in as FastAPI dependency +
a `users` table), voice input/output (would sit in front of the existing
`/api/chat/stream` contract — no backend change needed), and a dedicated
observability dashboard (logs are already structured; next step would be
shipping them to something like Grafana Loki, still free self-hosted).

## Notes on the safety guardrails in the tools
`network_tools.py` validates hostnames against a strict pattern before
shelling out to `ping`/`traceroute`, with hard timeouts — this prevents
command injection via a crafted "hostname" from a log or user message.
