"""
Fix: Build HNSW index — load vss FIRST, then set persistence flag
"""
import duckdb

DB_PATH = "../knowledge.duckdb"

con = duckdb.connect(DB_PATH)

# Must INSTALL+LOAD vss BEFORE setting the persistence flag
con.execute("INSTALL vss")
con.execute("LOAD vss")
con.execute("SET hnsw_enable_experimental_persistence = true")

# Drop old failed index if it exists
con.execute("DROP INDEX IF EXISTS hnsw_idx")

print("Building HNSW index (10-30 seconds)...")
con.execute("""
    CREATE INDEX hnsw_idx ON embeddings
    USING HNSW (embedding) WITH (metric='cosine')
""")
print("HNSW index built ✓")

total = con.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0]
print(f"Total chunks indexed: {total}")
con.close()
print("Phase 2 complete ✓")
