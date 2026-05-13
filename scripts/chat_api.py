"""
chat_api.py — Phase 4
FastAPI backend for the WorldMonitor chatbot.

Endpoints:
  POST /chat          — standard request/response
  POST /chat/stream   — streaming (Server-Sent Events)
  GET  /health        — health check
  GET  /history/{session_id}        — get conversation history
  DELETE /history/{session_id}/clear — clear conversation history

Session IDs are auto-generated UUIDs, returned on first response,
and sent back by the client on subsequent requests (transparently).
"""

import asyncio
import json
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

import duckdb
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# ── Path setup so imports work from any CWD ───────────────────────────────────
SCRIPTS_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPTS_DIR))

from session_store import store as session_store
from prompt_builder import build_prompt, SYSTEM_PROMPT
from retriever import retrieve

from google import genai
from google.genai import types

# ── Config ────────────────────────────────────────────────────────────────────
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL   = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash-lite")
DB_PATH        = str(SCRIPTS_DIR.parent / "knowledge.duckdb")
TOP_K          = 7
MAX_TOKENS     = 1024
TEMPERATURE    = 0.2

# ── Lifespan: warm up model + verify DB on startup ───────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Starting WorldMonitor Chat API...")
    if not GEMINI_API_KEY:
        print("WARNING: GEMINI_API_KEY not set — /chat will fail")
    # Warm up sentence-transformer (loads model into memory once)
    from retriever import _get_model
    _get_model()
    print("Embedding model loaded.")
    # Verify DB
    try:
        con = duckdb.connect(DB_PATH, read_only=True)
        con.execute("LOAD vss")
        count = con.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0]
        con.close()
        print(f"Knowledge base ready: {count:,} chunks indexed.")
        app.state.chunk_count = count
    except Exception as e:
        print(f"WARNING: Could not connect to DB: {e}")
        app.state.chunk_count = 0
    yield
    print("Shutting down.")

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="WorldMonitor Chat API",
    description="RAG-powered chatbot for the WorldMonitor knowledge base",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # tighten in production
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Schemas ───────────────────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    question: str
    session_id: str | None = None   # None = auto-generate

class ChatResponse(BaseModel):
    answer: str
    session_id: str
    sources: list[dict]
    model: str

class HistoryResponse(BaseModel):
    session_id: str
    messages: list[dict]

# ── Helpers ───────────────────────────────────────────────────────────────────
def _build_history_context(history: list[dict]) -> str:
    """Format past messages as a readable conversation block."""
    if not history:
        return ""
    lines = ["PREVIOUS CONVERSATION:"]
    for m in history:
        role = "User" if m["role"] == "user" else "Assistant"
        lines.append(f"{role}: {m['content']}")
    return "\n".join(lines) + "\n\n"


def _call_gemini(system_prompt: str, user_message: str) -> str:
    client = genai.Client(api_key=GEMINI_API_KEY)
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=user_message,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=TEMPERATURE,
            max_output_tokens=MAX_TOKENS,
        ),
    )
    return response.text.strip()


async def _stream_gemini(system_prompt: str, user_message: str):
    """Async generator yielding SSE-formatted chunks."""
    client = genai.Client(api_key=GEMINI_API_KEY)
    full_answer = []

    for chunk in client.models.generate_content_stream(
        model=GEMINI_MODEL,
        contents=user_message,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=TEMPERATURE,
            max_output_tokens=MAX_TOKENS,
        ),
    ):
        if chunk.text:
            full_answer.append(chunk.text)
            data = json.dumps({"type": "token", "content": chunk.text})
            yield f"data: {data}\n\n"
        await asyncio.sleep(0)   # yield control to event loop

    # Final event carries the complete answer (for session storage)
    yield f"data: {json.dumps({'type': 'done', 'full_answer': ''.join(full_answer)})}\n\n"


# ── Routes ────────────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {
        "status": "ok",
        "model": GEMINI_MODEL,
        "chunks_indexed": getattr(app.state, "chunk_count", 0),
        "active_sessions": session_store.active_count,
    }


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")
    if not GEMINI_API_KEY:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY not configured.")

    # Session
    session = session_store.get_or_create(req.session_id)
    history = session.get_history()

    # Retrieve
    chunks = retrieve(req.question, top_k=TOP_K, db_path=DB_PATH)

    # Build prompt — inject conversation history
    system_prompt, user_message = build_prompt(req.question, chunks)
    if history:
        user_message = _build_history_context(history) + user_message

    # Call LLM
    try:
        answer = _call_gemini(system_prompt, user_message)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LLM error: {str(e)}")

    # Store turn in session
    session.add("user", req.question)
    session.add("assistant", answer)

    return ChatResponse(
        answer=answer,
        session_id=session.session_id,
        sources=[
            {
                "chunk_id" : c["chunk_id"],
                "module"   : c["module"],
                "file_path": c["file_path"],
                "score"    : c["score"],
                "preview"  : c["content"][:200],
            }
            for c in chunks
        ],
        model=GEMINI_MODEL,
    )


@app.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")
    if not GEMINI_API_KEY:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY not configured.")

    session = session_store.get_or_create(req.session_id)
    history = session.get_history()
    chunks  = retrieve(req.question, top_k=TOP_K, db_path=DB_PATH)
    system_prompt, user_message = build_prompt(req.question, chunks)
    if history:
        user_message = _build_history_context(history) + user_message

    # Store user message immediately
    session.add("user", req.question)

    async def event_stream():
        # Send session_id and sources first so client has them immediately
        meta = json.dumps({
            "type"      : "meta",
            "session_id": session.session_id,
            "sources"   : [
                {
                    "chunk_id" : c["chunk_id"],
                    "module"   : c["module"],
                    "file_path": c["file_path"],
                    "score"    : c["score"],
                }
                for c in chunks
            ],
        })
        yield f"data: {meta}\n\n"

        full_answer = []
        async for event in _stream_gemini(system_prompt, user_message):
            yield event
            # Capture full answer from done event to store in session
            if '"type": "done"' in event:
                try:
                    payload = json.loads(event.replace("data: ", "").strip())
                    full_answer_text = payload.get("full_answer", "")
                    session.add("assistant", full_answer_text)
                except Exception:
                    pass

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/history/{session_id}", response_model=HistoryResponse)
async def get_history(session_id: str):
    history = session_store.get_history(session_id)
    if history is None:
        raise HTTPException(status_code=404, detail="Session not found.")
    return HistoryResponse(session_id=session_id, messages=history)


@app.delete("/history/{session_id}/clear")
async def clear_history(session_id: str):
    cleared = session_store.clear(session_id)
    if not cleared:
        raise HTTPException(status_code=404, detail="Session not found.")
    return {"status": "cleared", "session_id": session_id}


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    uvicorn.run(
        "chat_api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=[str(SCRIPTS_DIR)],
    )
