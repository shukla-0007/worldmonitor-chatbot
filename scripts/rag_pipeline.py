"""
rag_pipeline.py — Phase 3
Main RAG pipeline: retrieve → build prompt → call Gemini → return answer + sources.
Now supports profile-based personas: product, tech, support, sales.
"""

import os
import sys
from typing import List, Dict, Any

import duckdb
import google.generativeai as genai
from retriever import retrieve  # this is the function that returns that list 

# --- Model config ----------------------------------------------------------

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")

# Persona / profile configuration
PERSONAS: Dict[str, Dict[str, str]] = {
    "product": {
        "label": "Product",
        "system_instruction": (
            "You are a product manager for the WorldMonitor codebase. "
            "Explain features, capabilities, and user/business value in clear, non-technical language. "
            "Avoid code unless absolutely necessary. Base everything strictly on the retrieved files."
        ),
    },
    "tech": {
        "label": "Tech / Developer",
        "system_instruction": (
            "You are a senior developer working on the WorldMonitor codebase. "
            "Give architecture overviews, file paths, APIs, data flows, and implementation details. "
            "Reference modules, functions, and config taken from the retrieved code snippets."
        ),
    },
    "support": {
        "label": "Support",
        "system_instruction": (
            "You are a support engineer for WorldMonitor. "
            "Focus on troubleshooting, configuration, logs, environment issues, and common errors. "
            "Give step-by-step guidance based only on the retrieved documentation and code comments."
        ),
    },
    "sales": {
        "label": "Sales",
        "system_instruction": (
            "You are a sales engineer for WorldMonitor. "
            "Explain value propositions, use cases, differentiators, and deployment options "
            "based on the retrieved documentation (e.g., ARCHITECTURE, SELF_HOSTING, LICENSE)."
        ),
    },
}

DEFAULT_PERSONA = "product"


# --- DB / retrieval --------------------------------------------------------

from pathlib import Path

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent  # worldmonitor-chatbot root
DB_PATH = os.getenv(
    "RAG_DB_PATH",
    str(BASE_DIR / "knowledge.duckdb"),
)



def get_conn():
    return duckdb.connect(DB_PATH) 


def retrieve_chunks(query: str, top_k: int = 7) -> List[Dict[str, Any]]:
    """
    Retrieve top_k chunks using the existing retriever, which queries
    the `embeddings` table in knowledge.duckdb and returns:
      {
        "chunk_id": ...,
        "module": ...,
        "file_path": ...,
        "content": ...,
        "score": float,
      }
    """
    results = retrieve(query=query, top_k=top_k)

    chunks: List[Dict[str, Any]] = []
    for r in results:
        chunks.append(
            {
                "id": r["chunk_id"],
                "file_path": r["file_path"],
                "content": r["content"],
                "score": float(r["score"]),
            }
        )
    return chunks 



# --- Prompt building -------------------------------------------------------

def build_context_from_chunks(chunks: List[Dict[str, Any]]) -> str:
    lines = []
    for c in chunks:
        lines.append(f"File: {c['file_path']}")
        lines.append(c["content"])
        lines.append("-" * 40)
    return "\n".join(lines)


def build_prompt(question: str, chunks: List[Dict[str, Any]]) -> str:
    context = build_context_from_chunks(chunks)
    return (
        "You are answering questions about the GitHub repository 'koala73/worldmonitor'.\n"
        "Use ONLY the information in the CONTEXT below. If the answer is not in the context, say you do not know.\n\n"
        "CONTEXT:\n"
        f"{context}\n\n"
        "USER QUESTION:\n"
        f"{question}\n\n"
        "ANSWER:\n"
    )


# --- Main ask() entrypoint -------------------------------------------------

def ask(
    query: str,
    top_k: int = 7,
    verbose: bool = False,
    persona: str = DEFAULT_PERSONA,
) -> Dict[str, Any]:
    """
    Main RAG entrypoint.
    - Retrieves relevant chunks.
    - Builds a persona-aware prompt.
    - Calls Gemini and returns answer + sources + model + persona key.
    """
    persona_key = persona or DEFAULT_PERSONA
    persona_cfg = PERSONAS.get(persona_key, PERSONAS[DEFAULT_PERSONA])

    chunks = retrieve_chunks(query, top_k=top_k)
    prompt = build_prompt(query, chunks)

    if verbose:
        print(f"[persona={persona_key}] Retrieved {len(chunks)} chunks", file=sys.stderr)

    genai.configure(api_key=os.environ["GEMINI_API_KEY"])

    model = genai.GenerativeModel(
        model_name=GEMINI_MODEL,
        system_instruction=persona_cfg["system_instruction"],
    )

    resp = model.generate_content(prompt)

    answer_text = resp.text if hasattr(resp, "text") else str(resp)

    return {
        "answer": answer_text,
        "sources": chunks,
        "model": GEMINI_MODEL,
        "persona": persona_key,
    }


if __name__ == "__main__":
    query = " ".join(sys.argv[1:]).strip()
    if not query:
        print('Usage: python rag_pipeline.py "your question here"')
        sys.exit(1)

    result = ask(query=query, top_k=7, verbose=True)
    print(result["answer"])