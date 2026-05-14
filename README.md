# WorldMonitor Chatbot

A RAG (Retrieval-Augmented Generation) chatbot that answers questions grounded in the [WorldMonitor](https://github.com/koala73/worldmonitor) codebase and documentation.

**Live Demo:** https://huggingface.co/spaces/shukla1369/worldmonitor-chatbot

---

## What It Does

- Accepts natural language questions about WorldMonitor
- Retrieves the most relevant chunks from a pre-built vector knowledge base
- Generates grounded, cited answers via Google Gemini
- Supports multi-turn conversation with session memory
- Streams responses token by token in the UI

---

## Architecture

```
User Question
     │
     ▼
Embed query (all-MiniLM-L6-v2, 384-dim)
     │
     ▼
HNSW cosine search → Top-7 chunks (DuckDB + vss)
     │
     ▼
Build prompt: [system role] + [retrieved chunks] + [conversation history] + [question]
     │
     ▼
Gemini (gemini-2.0-flash) → Streamed answer
     │
     ▼
Chat UI (SSE streaming)
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Embedding model | `all-MiniLM-L6-v2` (sentence-transformers, local) |
| Vector DB | DuckDB + `vss` extension (HNSW cosine index) |
| LLM | Google Gemini (`gemini-2.0-flash`) |
| Backend | FastAPI + Uvicorn |
| Frontend | Vanilla HTML + JavaScript |
| Deployment | HuggingFace Spaces (Docker) |

---

## Project Structure

```
worldmonitor-chatbot/
├── Dockerfile                    # Container definition for HuggingFace
├── index.html                    # Chat UI
├── app.js                        # Frontend logic
├── knowledge.duckdb              # Pre-built vector DB (7,154 embeddings + HNSW index)
├── requirements.txt              # Python dependencies
├── docs/
│   ├── all_chunks.json           # 7,154 parsed chunks
│   └── kb_stats.json             # Knowledge base statistics
└── scripts/
    ├── ingest.py                 # Phase 1 — document chunking
    ├── embed_st.py               # Phase 2 — embedding runner
    ├── build_index.py            # Phase 2 — HNSW index builder
    ├── retriever.py              # Phase 3 — query embed + vector search
    ├── prompt_builder.py         # Phase 3 — prompt formatter
    ├── rag_pipeline.py           # Phase 3 — RAG orchestrator + Gemini call
    ├── session_store.py          # Phase 4 — in-memory session manager
    └── chat_api.py               # Phase 4+5 — FastAPI server + static file serving
```

---

## Prerequisites

- Python 3.11+
- A [Google Gemini API key](https://aistudio.google.com/app/apikey) (free tier)

---

## Local Setup

### 1. Clone the repo

```bash
git clone https://github.com/shukla1369/worldmonitor-chatbot.git
cd worldmonitor-chatbot
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Run the server

```bash
GEMINI_API_KEY="your_api_key_here" python scripts/chat_api.py
```

### 4. Open the UI

```
http://localhost:8000
```

That's it. No database setup needed — `knowledge.duckdb` is pre-built and included.

---

## API Reference

Base URL: `http://localhost:8000` (local) or the HuggingFace Space URL (production)

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/chat` | Standard request/response |
| `POST` | `/chat/stream` | Streaming via Server-Sent Events |
| `GET` | `/health` | Health check — model, chunks, active sessions |
| `GET` | `/history/{session_id}` | Retrieve conversation history |
| `DELETE` | `/history/{session_id}/clear` | Clear session history |

### Example request

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "What is WorldMonitor?"}'
```

### Example response

```json
{
  "answer": "WorldMonitor is a real-time monitoring platform that ...",
  "session_id": "a1b2c3d4-...",
  "sources": ["docs/overview.md", "docs/architecture.mdx"],
  "model": "gemini-2.0-flash"
}
```

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GEMINI_API_KEY` | ✅ Yes | Google Gemini API key |
| `GEMINI_MODEL` | ❌ Optional | Override model (default: `gemini-2.0-flash`) |

### Model options

| Model | When to use |
|---|---|
| `gemini-2.0-flash` | Default — fast, free tier |
| `gemini-2.5-flash` | Higher quality needed |
| `gemini-2.5-flash-lite` | When `gemini-2.0-flash` quota is exhausted |

## On HuggingFace: 
- `GEMINI_API_KEY` → add as **Secret** (private)
- `GEMINI_MODEL` → add as **Variable** (public, must be uppercase) 

--- 

## Knowledge Base

The vector knowledge base was built from the [WorldMonitor](https://github.com/koala73/worldmonitor) source repository.

| Metric | Value |
|---|---|
| Total chunks | 7,154 |
| Embedding model | `all-MiniLM-L6-v2` |
| Embedding dimensions | 384 |
| Vector similarity | Cosine (HNSW) |
| Top retrieval score | 0.77 |

### Chunk distribution by module

| Module | Chunks |
|---|---|
| documentation | 3,471 |
| frontend | 2,152 |
| server | 752 |
| api_contracts | 312 |
| database | 292 |
| api | 161 |
| root | 13 |
| scripts | 1 |

---


## Quota & Error Handling

When the daily Gemini quota is exhausted, the chatbot displays:
```
⚠️ 'gemini-2.5-flash' quota exhausted. Daily limit reached — please try again after 12:30 PM IST tomorrow.
```
No crash, no blank response — handled gracefully in both `/chat` and `/chat/stream`. 


## Deployment (HuggingFace Spaces)

The app is deployed as a Docker Space on HuggingFace.

```bash
# Add HuggingFace remote
git remote add hf https://huggingface.co/spaces/shukla1369/worldmonitor-chatbot

# Deploy
git push hf main
```

Set `GEMINI_API_KEY` in HuggingFace → Space Settings → Variables and secrets → New secret.

---

## Session Memory

- Sessions are auto-generated UUIDs, transparent to the user
- Last **6 turns** of conversation history are injected into every prompt
- Sessions expire after **1 hour** of inactivity
- No external database required — fully in-memory

---


Set secrets and variables in HuggingFace → Space Settings → Variables and secrets:
- **Secret:** `GEMINI_API_KEY`
- **Variable:** `GEMINI_MODEL` (uppercase)



## License

MIT


---
title: WorldMonitor Codebase Chatbot
emoji: 🌐
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---
# worldmonitor-chatbot
GitHub Codebase Knowledge Chatbot for koala73/worldmonitor
