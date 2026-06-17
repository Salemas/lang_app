import io
import json
import os
import uuid

import pandas as pd
from fastapi import APIRouter, File, Query, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from langchain_core.messages import AIMessage, HumanMessage
from pydantic import BaseModel
from sqlalchemy import select

from app.agents.graph import agent_graph
from app.config import get_model, set_model
from app.crud import (
    bulk_insert_pricelist_items,
    create_chat,
    create_pricelist_upload,
    delete_chat,
    delete_pricelist_upload,
    get_chats,
    get_messages,
    get_pricelist_uploads,
    search_pricelist_by_pn,
)
from app.db import async_session
from app.ingestion.document_processor import (
    delete_document,
    list_documents,
    process_and_store_document,
)
from app.models import Chat, Message

router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    chat_id: str


def chat_to_dict(c):
    return {
        "id": str(c.id),
        "title": c.title,
        "created_at": c.created_at.isoformat(),
        "updated_at": c.updated_at.isoformat(),
    }


def msg_to_dict(m):
    return {
        "id": str(m.id),
        "role": m.role,
        "content": m.content,
        "created_at": m.created_at.isoformat(),
    }


@router.get("/")
async def home():
    return "working"


@router.get("/health")
async def health():
    return {"status": "ok"}


class ModelRequest(BaseModel):
    model: str


OPENAI_MODELS = [
    "gpt-4o",
    "gpt-4o-mini",
    "gpt-4o-2024-08-06",
    "gpt-4o-mini-2024-07-18",
    "gpt-4-turbo",
    "gpt-4-turbo-2024-04-09",
    "gpt-4",
    "gpt-3.5-turbo",
]


@router.get("/settings/model")
async def get_current_model():
    return {"model": get_model(), "available_models": OPENAI_MODELS}


@router.put("/settings/model")
async def update_model(req: ModelRequest):
    if req.model not in OPENAI_MODELS:
        return JSONResponse(
            status_code=400,
            content={"error": f"Unknown model: {req.model}. Available: {', '.join(OPENAI_MODELS)}"},
        )
    set_model(req.model)
    return {"model": req.model}


@router.get("/chats")
async def list_chats():
    async with async_session() as db:
        chats = await get_chats(db)
    return [chat_to_dict(c) for c in chats]


@router.post("/chats")
async def new_chat():
    async with async_session() as db:
        chat = await create_chat(db)
    return chat_to_dict(chat)


@router.delete("/chats/{chat_id}")
async def remove_chat(chat_id: str):
    async with async_session() as db:
        await delete_chat(db, uuid.UUID(chat_id))
    return {"ok": True}


@router.get("/chats/{chat_id}/messages")
async def list_messages(chat_id: str):
    async with async_session() as db:
        msgs = await get_messages(db, uuid.UUID(chat_id))
    return [msg_to_dict(m) for m in msgs]


@router.post("/chat")
async def chat(req: ChatRequest):
    return StreamingResponse(
        stream_chat(req.message, req.chat_id),
        media_type="text/event-stream",
    )


async def stream_chat(message: str, chat_id_raw: str):
    cid = uuid.UUID(chat_id_raw)

    async with async_session() as db:
        result = await db.execute(select(Chat).where(Chat.id == cid))
        chat = result.scalar_one_or_none()
        if not chat:
            yield f"data: {json.dumps({'error': 'chat not found'})}\n\n"
            yield "data: [DONE]\n\n"
            return

        if chat.title == "New Chat":
            preview = message[:35] + "..." if len(message) > 35 else message
            chat.title = preview

        db.add(Message(chat_id=cid, role="user", content=message))
        await db.commit()

        history = await get_messages(db, cid)

    langchain_messages: list = [
        (HumanMessage if m.role == "user" else AIMessage)(content=m.content) for m in history
    ]

    full = ""
    async for event in agent_graph.astream_events(
        {"messages": langchain_messages},
        {"recursion_limit": 100},
        version="v2",
    ):
        if event["event"] == "on_chat_model_stream":
            metadata = event.get("metadata", {})
            if metadata.get("langgraph_node") == "respond":
                chunk = event["data"]["chunk"]
                if content := chunk.content:
                    full += content
                    yield f"data: {json.dumps({'content': content})}\n\n"

        if event["event"] == "on_chain_end" and event.get("name") == "respond":
            if not full:
                msgs = event["data"]["output"].get("messages", [])
                if msgs and hasattr(msgs[-1], "content"):
                    content = str(msgs[-1].content)
                    if content:
                        full = content
                        yield f"data: {json.dumps({'content': content})}\n\n"

    async with async_session() as db:
        if full:
            db.add(Message(chat_id=cid, role="assistant", content=full))
            await db.commit()

    yield "data: [DONE]\n\n"


ALLOWED_DOC_EXTENSIONS = {".pdf", ".pptx", ".ppt"}


@router.post("/documents/upload")
async def upload_document(file: UploadFile = File(...)):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_DOC_EXTENSIONS:
        return JSONResponse(
            status_code=400,
            content={
                "error": (
                    f"Unsupported file type: {ext}. Allowed: {', '.join(ALLOWED_DOC_EXTENSIONS)}"
                )
            },
        )
    content = await file.read()
    if len(content) > 20 * 1024 * 1024:
        return JSONResponse(status_code=413, content={"error": "File too large. Max 20MB."})
    try:
        result = process_and_store_document(file.filename, content)
        return result
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"Processing failed: {e}"})


@router.get("/documents")
async def list_uploaded_documents():
    return list_documents()


@router.delete("/documents/{doc_id}")
async def remove_document(doc_id: str):
    ok = delete_document(doc_id)
    if not ok:
        return JSONResponse(status_code=404, content={"error": "Document not found"})
    return {"ok": True}


COLUMN_ALIASES = {
    "pn": {"PN", "MPN", "PART NUMBER", "PART#", "PART #", "PARTNO", "PART NO"},
    "mnf": {"MNF", "MANUFACTURER", "VENDOR", "MAKER", "BRAND"},
    "description": {"DESCRIPTION", "DESC", "PART DESCRIPTION"},
    "moq_1": {"MOQ", "MOQ_1", "MOQ 1", "MINIMUM ORDER QUANTITY"},
    "price_1": {"PRICE", "PRICE_1", "PRICE 1", "UNIT PRICE"},
    "moq_2": {"MOQ_2", "MOQ 2"},
    "price_2": {"PRICE_2", "PRICE 2"},
    "moq_3": {"MOQ_3", "MOQ 3"},
    "price_3": {"PRICE_3", "PRICE 3"},
    "moq_4": {"MOQ_4", "MOQ 4"},
    "price_4": {"PRICE_4", "PRICE 4"},
    "leadtime": {"LEADTIME", "LEAD TIME", "LT"},
    "price_start": {"PRICE_START", "PRICE START", "VALID FROM", "EFFECTIVE FROM"},
    "price_end": {"PRICE_END", "PRICE END", "VALID TO", "VALID UNTIL", "EFFECTIVE TO"},
}

_ALIAS_LOOKUP = {}
for _target, _aliases in COLUMN_ALIASES.items():
    for _a in _aliases:
        _ALIAS_LOOKUP[_a] = _target


def _normalize_pricelist_columns(df: pd.DataFrame) -> pd.DataFrame:
    rename = {}
    for col in df.columns:
        key = col.strip().upper()
        if key in _ALIAS_LOOKUP:
            rename[col] = _ALIAS_LOOKUP[key]
    return df.rename(columns=rename)


@router.post("/pricelist/upload")
async def upload_pricelist(file: UploadFile = File(...)):
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        return JSONResponse(status_code=413, content={"error": "File too large. Max 10MB."})
    file.file = io.BytesIO(content)

    try:
        if file.filename.lower().endswith(".csv"):
            df = pd.read_csv(file.file)
        else:
            df = pd.read_excel(file.file, engine="openpyxl")
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": f"Could not parse file: {e}"})

    df = _normalize_pricelist_columns(df)
    if "pn" not in df.columns:
        return JSONResponse(status_code=400, content={"error": "Missing required column: PN"})
    for col in ("price_start", "price_end"):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce").dt.date
    df = df.where(pd.notna(df), None)
    records = df.to_dict(orient="records")

    async with async_session() as db:
        upload_id = uuid.uuid4()
        count = await bulk_insert_pricelist_items(db, records, upload_id=upload_id)
        if count:
            await create_pricelist_upload(
                db, file.filename or "unknown", count, upload_id=upload_id
            )
    return {"imported": count}


@router.delete("/pricelist/ingestions/{upload_id}")
async def remove_pricelist_upload(upload_id: str):
    async with async_session() as db:
        ok = await delete_pricelist_upload(db, uuid.UUID(upload_id))
    if not ok:
        return JSONResponse(status_code=404, content={"error": "Upload not found"})
    return {"ok": True}


@router.get("/pricelist/ingestions")
async def list_pricelist_uploads():
    async with async_session() as db:
        uploads = await get_pricelist_uploads(db)
    return [
        {
            "id": str(u.id),
            "filename": u.filename,
            "row_count": u.row_count,
            "uploaded_at": u.ingested_at.isoformat(),
        }
        for u in uploads
    ]


@router.get("/pricelist/search")
async def search_pricelist(q: str = Query(...), show_all: bool = Query(False, alias="all")):
    async with async_session() as db:
        results = await search_pricelist_by_pn(db, q, active_only=not show_all)
    return [
        {
            "pn": r.pn,
            "mnf": r.mnf,
            "description": r.description,
            "moq_1": r.moq_1,
            "price_1": r.price_1,
            "moq_2": r.moq_2,
            "price_2": r.price_2,
            "moq_3": r.moq_3,
            "price_3": r.price_3,
            "moq_4": r.moq_4,
            "price_4": r.price_4,
            "leadtime": r.leadtime,
            "price_start": str(r.price_start) if r.price_start else None,
            "price_end": str(r.price_end) if r.price_end else None,
            "ingested_at": r.ingested_at.isoformat() if r.ingested_at else None,
        }
        for r in results
    ]
