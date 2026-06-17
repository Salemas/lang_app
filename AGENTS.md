# lang_app

Multi-agent electronics distribution sales assistant. LangGraph supervisor pattern with FastAPI backend and Svelte 5 frontend.

## Dev servers (both must run)

```bash
# backend (uv)
cd backend && uv sync && uv run uvicorn app.main:app --reload --port 8000

# frontend (npm)
cd frontend && npm install && npm run dev
```

Frontend: `http://localhost:5173`, backed by Vite dev server + Svelte 5 (runes: `$state`, `$derived`, `mount`).  
Backend: `http://localhost:8000`, CORS allows `localhost:5173` only.  
Frontend API calls hardcode `http://localhost:8000`.  
No automated tests exist — verify manually.

## Key structure

- `backend/app/main.py` — FastAPI entry, loads `.env` (path relative to itself), sets up CORS + routes
- `backend/app/config.py` — in-memory model config (volatile, resets on restart)
- `backend/app/api/routes.py` — all REST + SSE endpoints
- `backend/app/agents/` — LangGraph supervisor + sub-agents (`supervisor.py`, `search.py`, `rag.py`, `document_rag.py`, `graph.py`)
- `backend/app/ingestion/document_processor.py` — PDF/PPTX extraction, chunking, ChromaDB storage
- `backend/app/db.py` — SQLAlchemy async engine, defaults to SQLite (`sqlite+aiosqlite:///./lang_app.db`)
- `backend/chroma_db/` — persistent vector store (auto-created, gitignored)
- `frontend/src/App.svelte` — monolithic SPA (chat UI + settings sidebar + pricelist/doc upload dialogs)
- `pricelists/` — sample CSV files for testing ingestion

## .env (project root)

Required: `OPENAI_API_KEY`, `TAVILY_API_KEY`.  
Optional: `DATABASE_URL` (defaults to SQLite), `LANGSMITH_API_KEY` (tracing).  
Loaded once in `main.py` via `load_dotenv(Path(__file__).resolve().parent.parent.parent / '.env')`.

## Agent architecture

Supervisor-based LangGraph `StateGraph` with routing to `search | rag | document_rag | FINISH`.  
Each sub-agent returns tagged results (`[Search Results]`, `[Pricelist Results]`, `[Document Results]`), collected by `respond` node for final LLM answer streamed via SSE.

### Agent roles

- **supervisor** — LLM router; scoped to electronics distribution queries only; out-of-scope → `FINISH` (polite refusal)
- **search** — ReAct agent using Tavily (tool-mandated, cannot answer from knowledge)
- **rag** — pricelist DB lookup by PN (read-only, PN extraction via LLM, anti-injection)
- **document_rag** — ChromaDB similarity search (no LLM call)
- **respond** — final LLM stream, role-locked, returns early if no agents were visited

All agent prompts include role locking + anti-injection guards.

## Data limits

| Upload | Max size | Formats |
|--------|----------|---------|
| Pricelist | 10 MB | .xlsx, .csv |
| Document | 20 MB | .pdf, .pptx, .ppt |

Pricelist columns mapped case-insensitively via `COLUMN_ALIASES` in `routes.py`.  
Documents chunked at 1000 chars (200 overlap) via `RecursiveCharacterTextSplitter`.

## Known issues

- Pydantic `UserWarning` about `SupervisorDecision.parsed` serialization — harmless
- No automated tests, no lint/typecheck config
- Model selection is in-memory only (volatile)
