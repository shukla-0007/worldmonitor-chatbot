"""
chat_api.py — Phase 4
FastAPI server wrapping the RAG pipeline with session memory and streaming.
"""

import os
import uuid
import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from session_store import SessionStore
from rag_pipeline import ask

# ── App ────────────────────────────────────────────────────────────────
app = FastAPI(title="WorldMonitor Chatbot API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

store = SessionStore()

# ── Models ─────────────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    question: str
    session_id: str | None = None

# ── Routes ─────────────────────────────────────────────────────────────
@app.post("/chat")
async def chat(req: ChatRequest):
    session = store.get_or_create(req.session_id)
    history = session.get_history()

    if history:
        history_text = "\n".join(
            f"{m['role'].upper()}: {m['content']}" for m in history[-6:]
        )
        full_query = f"Conversation so far:\n{history_text}\n\nNew question: {req.question}"
    else:
        full_query = req.question

    result = ask(full_query)
    session.add("user",      req.question)
    session.add("assistant", result["answer"])

    return {
        "answer":     result["answer"],
        "session_id": session.session_id,
        "sources":    [c["file_path"] for c in result["sources"]],
        "model":      result["model"],
    }
    

@app.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    session = store.get_or_create(req.session_id)

    async def event_generator():
        # Build a context-aware question from history
        history = session.get_history()
        if history:
            history_text = "\n".join(
                f"{m['role'].upper()}: {m['content']}" for m in history[-6:]
            )
            full_query = f"Conversation so far:\n{history_text}\n\nNew question: {req.question}"
        else:
            full_query = req.question

        result  = ask(full_query)
        sources = [c["file_path"] for c in result["sources"]]
        answer  = result["answer"]

        yield f"data: {json.dumps({'type': 'meta', 'session_id': session.session_id, 'sources': sources})}\n\n"

        words = answer.split(" ")
        for i, word in enumerate(words):
            chunk = word if i == 0 else " " + word
            yield f"data: {json.dumps({'type': 'token', 'content': chunk})}\n\n"

        session.add("user",      req.question)
        session.add("assistant", answer)
        yield f"data: {json.dumps({'type': 'done', 'full_answer': answer})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream") 

@app.get("/health") 
async def health():
    return {
        "status":          "ok",
        "model":           os.environ.get("GEMINI_MODEL", "gemini-2.5-flash-lite"),
        "chunks_indexed":  7154,
        "active_sessions": store.active_count, 
    }

@app.get("/history/{session_id}")
async def get_history(session_id: str):
    history = store.get_history(session_id)
    return {"session_id": session_id, "messages": history or []}

@app.delete("/history/{session_id}/clear")
async def clear_history(session_id: str):
    store.clear(session_id)
    return {"status": "cleared", "session_id": session_id}

# ── Static / UI — MUST be last ─────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent

@app.get("/")
async def serve_ui():
    return FileResponse(BASE_DIR / "index.html")

app.mount("/static", StaticFiles(directory=str(BASE_DIR)), name="static")

# ── Entry point ────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("chat_api:app", host="0.0.0.0", port=8000, reload=False) 