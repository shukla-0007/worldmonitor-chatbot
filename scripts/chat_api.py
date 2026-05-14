# chat_api.py — Phase 4/5
# FastAPI server wrapping RAG with per-profile sessions and streaming.
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))  # adds scripts/ to path 
import os
import json
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from session_store import SessionStore
from rag_pipeline import ask, PERSONAS, DEFAULT_PERSONA

BASE_DIR = Path(__file__).resolve().parent.parent  # project root
app = FastAPI()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files (index.html + app.js)
app.mount(
    "/static",
    StaticFiles(directory=BASE_DIR),
    name="static",
)


@app.get("/")
async def root():
    index_path = BASE_DIR / "index.html"
    if not index_path.exists():
        return {"error": "index.html does not exist at project root"}
    return FileResponse(index_path)


# --- Models / store --------------------------------------------------------

class ChatRequest(BaseModel):
    question: str
    session_id: str | None = None
    profile: str | None = None  # "product" | "tech" | "support" | "sales"


store = SessionStore()


def normalize_profile(profile: str | None) -> str:
    key = (profile or "").strip().lower()
    if key in PERSONAS:
        return key
    return DEFAULT_PERSONA


# --- Plain /chat endpoint --------------------------------------------------

@app.post("/chat")
async def chat(req: ChatRequest):
    profile = normalize_profile(req.profile)
    session = store.get_or_create(profile=profile, session_id=req.session_id)

    session.add("user", req.question)

    result = ask(
        query=req.question,
        top_k=7,
        verbose=False,
        persona=profile,
    )

    session.add("assistant", result["answer"])

    return {
        "answer": result["answer"],
        "sources": result["sources"],
        "session_id": session.id,
        "profile": profile,
        "model": result["model"],
    }


# --- Streaming /chat/stream endpoint (SSE) --------------------------------

async def stream_events(question: str, profile: str, session_id: str | None) -> AsyncGenerator[bytes, None]:
    """
    Simple pseudo-streaming: send one meta event for sources, then one event for answer.
    You can later replace with true token streaming if you want.
    """
    session = store.get_or_create(profile=profile, session_id=session_id)
    session.add("user", question)

    result = ask(
        query=question,
        top_k=7,
        verbose=False,
        persona=profile,
    )

    session.add("assistant", result["answer"])

    # meta event: sources + metadata
    meta_payload = {
        "type": "meta",
        "session_id": session.id,
        "profile": profile,
        "model": result["model"],
        "sources": result["sources"],
    }
    yield f"event: meta\ndata: {json.dumps(meta_payload)}\n\n".encode("utf-8")

    # content event: full answer in one chunk
    answer_payload = {
        "type": "answer",
        "content": result["answer"],
    }
    yield f"event: message\ndata: {json.dumps(answer_payload)}\n\n".encode("utf-8")


@app.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    profile = normalize_profile(req.profile)
    event_generator = stream_events(
        question=req.question,
        profile=profile,
        session_id=req.session_id,
    )
    return StreamingResponse(
        event_generator,
        media_type="text/event-stream",
    )


# --- History and health ----------------------------------------------------

@app.get("/history/{profile}/{session_id}")
async def get_history(profile: str, session_id: str):
    profile_key = normalize_profile(profile)
    session = store.get(profile_key, session_id)
    if not session:
        return {"session_id": session_id, "profile": profile_key, "messages": []}
    return session.to_dict()


@app.delete("/history/{profile}/{session_id}/clear")
async def clear_history(profile: str, session_id: str):
    profile_key = normalize_profile(profile)
    store.clear(profile_key, session_id)
    return {"ok": True}


@app.get("/health")
async def health():
    store.cleanup_expired()
    return {
        "status": "ok",
        "active_sessions": store.active_count,
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("chat_api:app", host="0.0.0.0", port=port, reload=False) 
    
    
    