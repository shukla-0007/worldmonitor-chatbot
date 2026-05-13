"""
Phase 1: Codebase Ingestion Script
"""

import json
import re
import subprocess
import sys
from pathlib import Path

REPO_URL    = "https://github.com/koala73/worldmonitor.git"
REPO_DIR    = Path("./worldmonitor_repo")
OUTPUT_DIR  = Path("../docs")
SAMPLE_OUT  = OUTPUT_DIR / "sample_knowledge_base.json"
CHUNKS_OUT  = OUTPUT_DIR / "all_chunks.json"

MAX_CHUNK_CHARS = 3200
OVERLAP_CHARS   = 400

SKIP_DIRS = {
    "node_modules", ".git", "dist", "build", ".next", "out",
    ".turbo", "coverage", ".cache", "__pycache__", ".venv", "target",
}
SKIP_FILES = {"package-lock.json", "yarn.lock", "pnpm-lock.yaml", ".DS_Store"}

INCLUDE_EXT = {
    ".ts", ".tsx", ".js", ".jsx", ".md", ".mdx",
    ".json", ".proto", ".toml", ".yaml", ".yml",
    ".css", ".html", ".rs",
}

EXT_LANG = {
    ".ts":"typescript", ".tsx":"typescript",
    ".js":"javascript", ".jsx":"javascript",
    ".md":"markdown",   ".mdx":"markdown",
    ".json":"json",     ".proto":"protobuf",
    ".toml":"toml",     ".yaml":"yaml", ".yml":"yaml",
    ".css":"css",       ".html":"html", ".rs":"rust",
}

def detect_module(p):
    p = p.lower()
    if "/api/" in p or p.startswith("api/"):  return "api"
    if "/proto/" in p:                         return "api_contracts"
    if "/server/" in p:                        return "server"
    if "/convex/" in p:                        return "database"
    if "/src/" in p:                           return "frontend"
    if "/scripts/" in p:                       return "scripts"
    if "/docs/" in p:                          return "documentation"
    if "dockerfile" in p or "/docker/" in p:   return "deployment"
    if "/shared/" in p:                        return "shared"
    if "/tests/" in p or "/e2e/" in p:        return "testing"
    if "/src-tauri/" in p:                     return "desktop"
    if any(x in p for x in ["readme","architecture","contributing","agents","changelog"]):
        return "documentation"
    return "root"

def generate_tags(content, fp):
    tags, cl = set(), content.lower()
    if any(x in cl for x in ["auth","login","jwt","session","oauth"]): tags.add("auth")
    if any(x in cl for x in ["api","fetch","endpoint","route","http"]): tags.add("api")
    if any(x in cl for x in ["map","globe","deck.gl","maplibre","layer"]): tags.add("maps")
    if any(x in cl for x in ["ai","ollama","groq","llm","openrouter","model"]): tags.add("ai")
    if any(x in cl for x in ["finance","stock","crypto","commodity","market"]): tags.add("finance")
    if any(x in cl for x in ["news","feed","rss","article"]): tags.add("news")
    if any(x in cl for x in ["cache","redis","upstash"]): tags.add("caching")
    if any(x in cl for x in ["deploy","docker","vercel","railway","nginx"]): tags.add("deployment")
    if any(x in cl for x in ["component","react","usestate","useeffect"]): tags.add("frontend")
    if any(x in cl for x in ["tauri","rust","desktop"]): tags.add("desktop")
    if any(x in cl for x in ["test","spec","describe","expect"]): tags.add("testing")
    if any(x in cl for x in ["config","env","environment","settings"]): tags.add("config")
    if ".proto" in fp: tags.add("api_contracts")
    if ".md" in fp: tags.add("documentation")
    return sorted(tags) if tags else ["general"]

def chunk_by_size(text):
    chunks, start = [], 0
    while start < len(text):
        c = text[start:start+MAX_CHUNK_CHARS].strip()
        if c: chunks.append(c)
        start += MAX_CHUNK_CHARS - OVERLAP_CHARS
    return chunks

def chunk_file(content, ext):
    if ext in (".md", ".mdx"):
        parts = re.split(r'\n(?=#{1,3} )', content)
        out = []
        for s in parts:
            s = s.strip()
            if len(s) < 50: continue
            out.extend(chunk_by_size(s) if len(s) > MAX_CHUNK_CHARS else [s])
        return out
    if ext in (".json", ".toml", ".yaml", ".yml", ".proto"):
        return [content.strip()] if len(content) <= MAX_CHUNK_CHARS else chunk_by_size(content)
    # code
    pat = r'\n(?=(?:export\s+)?(?:async\s+)?(?:function|class|const|let|var|interface|type|enum)\s+\w)'
    sections = re.split(pat, content)
    cur, chunks = "", []
    for s in sections:
        if len(cur)+len(s) < MAX_CHUNK_CHARS:
            cur += s
        else:
            if cur.strip(): chunks.append(cur.strip())
            cur = s
    if cur.strip(): chunks.append(cur.strip())
    out = []
    for c in chunks:
        out.extend(chunk_by_size(c) if len(c) > MAX_CHUNK_CHARS else [c])
    return [c for c in out if len(c) > 30]

def walk_repo(repo_dir):
    files = []
    for abs_path in sorted(repo_dir.rglob("*")):
        # Skip non-files and unresolvable symlinks
        try:
            if not abs_path.is_file():
                continue
        except OSError:
            continue

        rel = abs_path.relative_to(repo_dir)

        # Skip unwanted dirs
        skip = False
        for part in rel.parts:
            if part in SKIP_DIRS:
                skip = True
                break
        if skip: continue
        if abs_path.name in SKIP_FILES: continue

        ext = abs_path.suffix.lower()
        if ext not in INCLUDE_EXT: continue

        # Skip huge JSON files
        try:
            if ext == ".json" and abs_path.stat().st_size > 100_000:
                continue
        except OSError:
            continue

        try:
            content = abs_path.read_text(encoding="utf-8", errors="ignore")
            if len(content.strip()) < 20: continue
            files.append((str(rel), content, ext))
        except OSError:
            continue
    return files

def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if not REPO_DIR.exists():
        print(f"Cloning {REPO_URL} ...")
        r = subprocess.run(["git","clone","--depth=1",REPO_URL,str(REPO_DIR)],
                           capture_output=True, text=True)
        if r.returncode != 0:
            print(f"Clone failed:\n{r.stderr}"); sys.exit(1)
        print("Clone complete.")
    else:
        print(f"Repo already exists at {REPO_DIR}, skipping clone.")

    print("Walking repository files...")
    raw_files = walk_repo(REPO_DIR)
    print(f"Found {len(raw_files)} eligible files.")

    all_chunks, chunk_id = [], 0
    for rel_path, content, ext in raw_files:
        for i, text in enumerate(chunk_file(content, ext)):
            all_chunks.append({
                "chunk_id":    f"chunk_{chunk_id:05d}",
                "file_path":   rel_path,
                "module":      detect_module(rel_path),
                "language":    EXT_LANG.get(ext, "text"),
                "chunk_index": i,
                "content":     text,
                "tags":        generate_tags(text, rel_path),
                "char_count":  len(text),
            })
            chunk_id += 1

    print(f"Total chunks: {len(all_chunks)}")

    with open(CHUNKS_OUT, "w", encoding="utf-8") as f:
        json.dump(all_chunks, f, indent=2, ensure_ascii=False)

    # 10 diverse samples
    seen, samples = set(), []
    for c in all_chunks:
        if c["module"] not in seen:
            samples.append(c); seen.add(c["module"])
        if len(samples) == 10: break
    while len(samples) < 10 and len(samples) < len(all_chunks):
        for c in all_chunks:
            if c not in samples: samples.append(c)
            if len(samples) == 10: break

    with open(SAMPLE_OUT, "w", encoding="utf-8") as f:
        json.dump(samples, f, indent=2, ensure_ascii=False)

    modules = {}
    for c in all_chunks:
        modules[c["module"]] = modules.get(c["module"], 0) + 1

    print("\n=== INGESTION STATS ===")
    print(f"Total files processed : {len(raw_files)}")
    print(f"Total chunks          : {len(all_chunks)}")
    avg = sum(c['char_count'] for c in all_chunks) // max(len(all_chunks), 1)
    print(f"Avg chunk size (chars): {avg}")
    print("\nChunks per module:")
    for mod, count in sorted(modules.items(), key=lambda x: -x[1]):
        print(f"  {mod:<20} {count}")
    print("\nPhase 1 complete. Run embed.py next.")

if __name__ == "__main__":
    main() 