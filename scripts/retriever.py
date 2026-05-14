"""
retriever.py — Phase 3
Embeds a query using all-MiniLM-L6-v2 and retrieves top-K chunks
from knowledge.duckdb via HNSW cosine search.
"""

import duckdb
from sentence_transformers import SentenceTransformer 

from pathlib import Path
DB_PATH = str(Path(__file__).resolve().parent.parent / "knowledge.duckdb") 
EMBED_MODEL = "all-MiniLM-L6-v2"
TOP_K       = 7

_model = None  # lazy-loaded singleton

def _get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer(EMBED_MODEL)
    return _model

def embed_query(query: str) -> list[float]:
    model = _get_model()
    vec = model.encode(
        query,
        normalize_embeddings=True,
        convert_to_numpy=True,
    )
    return vec.tolist()

def retrieve(query: str, top_k: int = TOP_K, db_path: str = DB_PATH) -> list[dict]:
    """
    Returns a list of top_k dicts:
      { chunk_id, module, file_path, content, score }
    sorted by descending cosine similarity.
    """
    query_vec = embed_query(query)

    con = duckdb.connect(db_path) 
    con.execute("INSTALL vss")
    con.execute("LOAD vss")
    con.execute("SET hnsw_enable_experimental_persistence = true") 

    rows = con.execute(
        """
        SELECT
            chunk_id,
            module,
            file_path,
            content,
            array_cosine_similarity(embedding, $1::FLOAT[384]) AS score
        FROM embeddings
        ORDER BY score DESC
        LIMIT $2
        """,
        [query_vec, top_k],
    ).fetchall()
    con.close()

    return [
        {
            "chunk_id" : row[0],
            "module"   : row[1],
            "file_path": row[2],
            "content"  : row[3],
            "score"    : round(float(row[4]), 4),
        }
        for row in rows
    ]


if __name__ == "__main__":
    import sys, json
    q = " ".join(sys.argv[1:]) or "What is WorldMonitor?"
    results = retrieve(q)
    print(f"\nQuery: {q}\n")
    for i, r in enumerate(results, 1):
        print(f"[{i}] score={r['score']}  module={r['module']}")
        print(f"    {r['content'][:200].strip()}...")
        print()
