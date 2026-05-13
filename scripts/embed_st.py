"""
Phase 2 — Local Embedding via sentence-transformers
Model  : all-MiniLM-L6-v2  (~90MB, 384-dim)
RAM    : ~150MB peak
Speed  : ~500-800 chunks/sec on M1 CPU  →  ~20-30 seconds total
No API, no rate limits, no internet after first download
"""

import os, sys, json, time
import numpy as np
import duckdb
from tqdm import tqdm

CHUNKS_FILE = "../docs/all_chunks.json"
DB_PATH     = "../knowledge.duckdb"
EMBED_MODEL = "all-MiniLM-L6-v2"
VECTOR_DIM  = 384
BATCH_SIZE  = 64   # small batches → low RAM, no hang

def main():
    # Load sentence-transformers lazily to catch import errors early
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        sys.exit("Run: pip install sentence-transformers")

    print(f"Loading chunks from {CHUNKS_FILE}...")
    with open(CHUNKS_FILE) as f:
        chunks = json.load(f)
    print(f"Loaded {len(chunks)} chunks.")

    # Init DuckDB
    con = duckdb.connect(DB_PATH)
    con.execute(f"""
        CREATE TABLE IF NOT EXISTS embeddings (
            chunk_id  TEXT PRIMARY KEY,
            module    TEXT,
            file_path TEXT,
            content   TEXT,
            embedding FLOAT[{VECTOR_DIM}]
        )
    """)

    # Resume support
    done      = set(r[0] for r in con.execute("SELECT chunk_id FROM embeddings").fetchall())
    remaining = [c for c in chunks if c["chunk_id"] not in done]
    print(f"Already done: {len(done)} | Remaining: {len(remaining)}")

    if not remaining:
        print("All chunks already embedded!")
        con.close(); return

    # Load model — ~90MB, loads in ~3s on M1
    print(f"\nLoading model: {EMBED_MODEL}  (~90MB, one-time download)")
    model = SentenceTransformer(EMBED_MODEL)
    print("Model ready.\n")

    # Embed in small batches — keeps RAM flat, no spikes
    t0      = time.time()
    skipped = 0

    for i in tqdm(range(0, len(remaining), BATCH_SIZE),
                  desc="Embedding",
                  total=(len(remaining) + BATCH_SIZE - 1) // BATCH_SIZE):

        batch = remaining[i : i + BATCH_SIZE]
        texts = [c["content"] for c in batch]

        try:
            # show_progress_bar=False avoids nested bars
            embs = model.encode(
                texts,
                batch_size=BATCH_SIZE,
                show_progress_bar=False,
                normalize_embeddings=True,   # cosine similarity ready
                convert_to_numpy=True,
            )
        except Exception as e:
            print(f"\nBatch {i} failed: {e} — skipping")
            skipped += len(batch)
            continue

        rows = [
            (
                batch[j]["chunk_id"],
                batch[j].get("module", ""),
                batch[j].get("file_path", ""),
                batch[j]["content"],
                embs[j].tolist(),
            )
            for j in range(len(batch))
        ]
        con.executemany(
            "INSERT OR REPLACE INTO embeddings VALUES (?,?,?,?,?)", rows
        )
        con.commit()

    elapsed = time.time() - t0

    # Build HNSW index
    print("\nBuilding HNSW index...")
    con.execute("INSTALL vss; LOAD vss;")
    con.execute("""
        CREATE INDEX IF NOT EXISTS hnsw_idx ON embeddings
        USING HNSW (embedding) WITH (metric='cosine')
    """)
    print("HNSW index built.")

    # Final stats
    total = con.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0]
    print(f"\n=== PHASE 2 STATS ===")
    print(f"Total chunks in DB : {total}")
    print(f"Skipped            : {skipped}")
    print(f"Embedding model    : {EMBED_MODEL} (local)")
    print(f"Vector dimensions  : {VECTOR_DIM}")
    print(f"Time taken         : {elapsed:.1f}s  ({len(remaining)/elapsed:.0f} chunks/sec)")

    print("\nChunks per module:")
    for row in con.execute(
        "SELECT module, COUNT(*) FROM embeddings GROUP BY module ORDER BY 2 DESC"
    ).fetchall():
        print(f"  {row[0]:<40} {row[1]}")

    stats = {
        "total_chunks"   : total,
        "skipped"        : skipped,
        "embedding_model": EMBED_MODEL,
        "vector_dim"     : VECTOR_DIM,
        "time_seconds"   : round(elapsed, 1),
        "source"         : "local-sentence-transformers",
    }
    os.makedirs("../docs", exist_ok=True)
    with open("../docs/kb_stats.json", "w") as f:
        json.dump(stats, f, indent=2)
    print("\nStats saved to ../docs/kb_stats.json")
    print("Phase 2 complete ✓")
    con.close()

if __name__ == "__main__":
    main()
