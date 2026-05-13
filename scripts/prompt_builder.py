"""
prompt_builder.py — Phase 3
Builds the system prompt and user message from retrieved chunks.
"""

SYSTEM_PROMPT = """You are the WorldMonitor AI assistant — an expert on all WorldMonitor products, modules, workflows, and documentation.

Your job is to answer user questions accurately and helpfully using ONLY the context provided below. The context is made up of relevant excerpts retrieved from the official WorldMonitor knowledge base.

Guidelines:
- Answer directly and concisely. Lead with the answer, then explain.
- If the context contains the answer, use it fully. Quote or reference specific details where useful.
- If the context does NOT contain enough information to answer confidently, say: "I don't have enough information in the knowledge base to answer that fully." Do NOT make up information.
- Do not mention "the context", "the excerpts", or "retrieved chunks" in your answer — respond as a knowledgeable assistant, not as a system describing its process.
- Use markdown formatting (bullet points, bold, code blocks) where it improves clarity.
- Be professional, clear, and helpful."""


def build_prompt(query: str, chunks: list[dict]) -> tuple[str, str]:
    """
    Returns (system_prompt, user_message) ready for Gemini.
    """
    context_parts = []
    for i, chunk in enumerate(chunks, 1):
        source = chunk.get("module") or chunk.get("file_path") or "Unknown"
        context_parts.append(
            f"--- Excerpt {i} (Source: {source}) ---\n{chunk['content'].strip()}"
        )

    context_block = "\n\n".join(context_parts)

    user_message = f"""CONTEXT FROM KNOWLEDGE BASE:
{context_block}

---

USER QUESTION:
{query}"""

    return SYSTEM_PROMPT, user_message
