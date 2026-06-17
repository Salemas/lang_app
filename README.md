# multi_agent_app

Multi-agent electronics distribution sales assistant. Uses LangGraph's supervisor pattern to route queries to the right agent — web search, pricelist lookup, or document search — then synthesizes a response.

## Quick start

### Prerequisites

- Python >= 3.11 with [uv](https://docs.astral.sh/uv/)
- Node.js (for the frontend)
- API keys: [OpenAI](https://platform.openai.com/api-keys), [Tavily](https://tavily.com)

### Setup

```bash
cp .env.example .env   # fill in your API keys
```

```bash
# backend
cd backend && uv sync && uv run uvicorn app.main:app --reload --port 8000

# frontend (separate terminal)
cd frontend && npm install && npm run dev
```

Open `http://localhost:5173` in a browser. Both servers must be running.

## How it works

A user message hits the FastAPI backend (`POST /chat`), which streams a response via SSE.

Behind the scenes, a LangGraph `StateGraph` decides what to do:

```
User → supervisor → search / rag / document_rag → respond → streamed answer
```

The **supervisor** (LLM router) decides which sub-agent to call based on the query. Sub-agents tag their results (`[Search Results]`, `[Pricelist Results]`, `[Document Results]`), and the **respond** node produces the final answer from all gathered information.

| Agent | What it does |
|-------|-------------|
| supervisor | Routes queries; rejects out-of-scope topics |
| search | Web search via Tavily (ReAct agent) |
| rag | Pricelist database lookup by part number |
| document_rag | ChromaDB similarity search over uploaded PDFs/PPTs |
| respond | Composes final answer from agent outputs |

## Features

- **Chat** — persistent conversations stored in SQLite
- **Pricelist upload** — import .xlsx/.csv files (case-insensitive column mapping)
- **Document upload** — index .pdf/.pptx files into ChromaDB for retrieval
- **Model selection** — switch OpenAI models from the UI (in-memory, resets on restart)

## Project structure

```
backend/
  app/
    main.py               # FastAPI entry point
    api/routes.py         # All REST + SSE endpoints
    agents/               # LangGraph supervisor + sub-agents
    ingestion/            # PDF/PPTX extraction, ChromaDB storage
    db.py                 # SQLAlchemy async engine (SQLite default)
    models.py             # Chat, Message, PricelistItem ORM models
    crud.py               # Database CRUD helpers
  chroma_db/              # Vector store (auto-created, gitignored)
frontend/
  src/
    App.svelte            # Monolithic chat UI + settings + uploads
    main.js               # Svelte 5 mount point
```

## API overview

| Endpoint | Purpose |
|----------|---------|
| `POST /chat` | Send message, stream response via SSE |
| `GET/POST/DELETE /chats` | Manage conversations |
| `POST /pricelist/upload` | Import .xlsx/.csv (max 10 MB) |
| `GET /pricelist/search?q=PN` | Look up part number |
| `POST /documents/upload` | Upload .pdf/.pptx (max 20 MB) |
| `GET/PUT /settings/model` | View/change OpenAI model |

Full endpoint details in `backend/app/api/routes.py`.

## Tech stack

- **Python** — FastAPI, LangGraph, LangChain, SQLAlchemy, ChromaDB
- **Frontend** — Svelte 5, Vite
- **Search** — Tavily API
- **LLM** — OpenAI (configurable model)
