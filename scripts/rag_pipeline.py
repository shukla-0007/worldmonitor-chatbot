"""
rag_pipeline.py — Phase 3
Main RAG pipeline: retrieve → build prompt → call Gemini → return answer.
CLI testable: python rag_pipeline.py "your question here"
"""

import os
import sys
from retriever import retrieve
from prompt_builder import build_prompt
from google import genai
from google.genai import types

GEMINI_MODEL   = "gemini-2.5-flash-lite"
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

def ask(query: str, top_k: int = 7, verbose: bool = False) -> dict:
    """
    Full RAG pipeline for a single query.

    Returns:
      {
        "query"    : str,
        "answer"   : str,
        "sources"  : list[dict],   # retrieved chunks with scores
        "model"    : str,
      }
    """
    if not GEMINI_API_KEY:
        raise EnvironmentError("GEMINI_API_KEY environment variable is not set.")

    # Step 1 — Retrieve
    if verbose:
        print(f"[retriever] Embedding query and searching top-{top_k} chunks...")
    chunks = retrieve(query, top_k=top_k)

    if verbose:
        print(f"[retriever] Retrieved {len(chunks)} chunks:")
        for c in chunks:
            print(f"  score={c['score']}  module={c['module']}  chunk={c['chunk_id']}")

    # Step 2 — Build prompt
    system_prompt, user_message = build_prompt(query, chunks)

    if verbose:
        print(f"\n[prompt_builder] Prompt built. Calling {GEMINI_MODEL}...\n")

    # Step 3 — Call Gemini
    client = genai.Client(api_key=GEMINI_API_KEY)
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=user_message,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.2,        # low temp = factual, grounded answers
            max_output_tokens=1024,
        ),
    )

    answer = response.text.strip()

    return {
        "query"  : query,
        "answer" : answer,
        "sources": chunks,
        "model"  : GEMINI_MODEL,
    }


if __name__ == "__main__":
    query = " ".join(sys.argv[1:]).strip()
    if not query:
        print("Usage: python rag_pipeline.py \"your question here\"")
        sys.exit(1)

    print(f"\n{'='*60}")
    print(f"Query: {query}")
    print(f"{'='*60}\n")

    result = ask(query, verbose=True)

    print("ANSWER:")
    print("-" * 40)
    print(result["answer"])
    print("-" * 40)

    print(f"\nSOURCES ({len(result['sources'])} chunks retrieved):")
    for i, src in enumerate(result["sources"], 1):
        print(f"  [{i}] score={src['score']}  {src['module'] or src['file_path']}")

    print(f"\nModel: {result['model']}")
