# scripts/sample_kb.py
import json
from pathlib import Path
from collections import defaultdict

BASE_DIR = Path(__file__).resolve().parent.parent
chunks_path = BASE_DIR / "docs" / "all_chunks.json"
output_path = BASE_DIR / "docs" / "sample_knowledge_base.json"

with open(chunks_path, "r") as f:
    all_chunks = json.load(f)

# Group by module
by_module = defaultdict(list)
for chunk in all_chunks:
    by_module[chunk["module"]].append(chunk)

# Pick 3 best chunks per module (first 3 — already ordered by file)
MODULES = ["documentation", "server", "api", "database", "frontend", "api_contracts", "root"]
sample = []
for module in MODULES:
    chunks = by_module.get(module, [])[:3]
    for c in chunks:
        sample.append({
            "chunk_id": c["chunk_id"],
            "module": c["module"],
            "file_path": c["file_path"],
            "content": c["content"][:500] + ("..." if len(c["content"]) > 500 else ""),
        })

with open(output_path, "w") as f:
    json.dump(sample, f, indent=2)

print(f"Saved {len(sample)} sample chunks to {output_path}") 