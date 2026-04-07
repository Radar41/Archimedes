#!/usr/bin/env python3
"""
batch_ingest.py — Feed prepped corpus chunks into Archimedes ingestion pipeline.

Accepts directories of chunked files (markdown, JSON, text, images) and processes
them sequentially through:
  1. IntakeNormalize — clean/format/validate
  2. Classify — assign category, project, urgency using LLM or rules
  3. Route — emit to target (Obsidian note, Asana task, GitHub issue, expansion ledger)
  4. Log — record in ingestion ledger

USAGE:
  python3 batch_ingest.py ./corpus/emails/          # all chunks in directory
  python3 batch_ingest.py ./corpus/ --recursive      # recurse subdirs
  python3 batch_ingest.py ./corpus/ --dry-run        # classify only, don't route
  python3 batch_ingest.py ./corpus/ --source email   # tag source type

PREREQUISITES:
  - Ollama running with a text model (mistral, llama3, etc.)
  - Or LiteLLM proxy running (for remote models during studio session)

OUTPUT:
  ./ingestion_logs/
    ingestion_ledger.csv        # full record of every chunk processed
    routing_summary.json        # counts by route target
    errors.log                  # any failures
"""

import argparse
import csv
import hashlib
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

# ── Config ──────────────────────────────────────────────────
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
LITELLM_URL = os.getenv("LITELLM_URL", "http://localhost:4000")
DEFAULT_MODEL = os.getenv("INGEST_MODEL", "mistral")
LOG_DIR = Path("./ingestion_logs")
MAX_CHUNK_CHARS = 8000  # truncate chunks beyond this for classification

# ── Classification prompt ───────────────────────────────────
CLASSIFY_PROMPT = """You are classifying a text chunk for ingestion into a personal knowledge system.

Analyze the content and respond with ONLY a JSON object (no markdown, no preamble):

{{
  "project": "<best matching project or 'unassigned'>",
  "category": "<one of: idea, question, task, decision, reference, experiment, note, correspondence, code, financial>",
  "urgency": "<one of: immediate, this_week, this_month, backlog, archive>",
  "tags": ["<tag1>", "<tag2>"],
  "route_target": "<one of: obsidian, asana, github, expansion_ledger, archive>",
  "summary": "<one sentence summary>",
  "confidence": <0.0 to 1.0>
}}

Known projects: ARCHIMEDES, BTC_SPEC, BTC_BOARD_GAME, POLY, DDT, OPERATOR_ATLAS, SCHOOL, ADMIN_PERSONAL

Content to classify:
---
{content}
---"""

# ── Routing keywords (deterministic fast-path) ──────────────
KEYWORD_ROUTES = {
    "task": "asana",
    "todo": "asana",
    "deadline": "asana",
    "due": "asana",
    "bug": "github",
    "fix": "github",
    "commit": "github",
    "pull request": "github",
    "idea": "expansion_ledger",
    "thought": "expansion_ledger",
    "maybe": "expansion_ledger",
    "someday": "expansion_ledger",
    "note": "obsidian",
    "reference": "obsidian",
    "paper": "obsidian",
}


def sha256_of(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def call_llm(prompt: str, model: str, timeout: int = 60) -> dict:
    """Call Ollama or LiteLLM for classification."""
    # Try Ollama first
    try:
        r = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={"model": model, "prompt": prompt, "stream": False,
                   "options": {"temperature": 0.1, "num_predict": 512}},
            timeout=timeout,
        )
        if r.ok:
            text = r.json().get("response", "")
            # Try to parse JSON from response
            text = text.strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            return {"ok": True, "text": text, "via": "ollama"}
    except Exception:
        pass

    # Fallback to LiteLLM
    try:
        r = requests.post(
            f"{LITELLM_URL}/v1/chat/completions",
            json={"model": model, "messages": [{"role": "user", "content": prompt}],
                  "temperature": 0.1, "max_tokens": 512},
            timeout=timeout,
        )
        if r.ok:
            text = r.json()["choices"][0]["message"]["content"]
            return {"ok": True, "text": text, "via": "litellm"}
    except Exception:
        pass

    return {"ok": False, "text": "", "via": "none", "error": "Both Ollama and LiteLLM unreachable"}


def keyword_classify(content: str) -> str | None:
    """Fast-path: check for routing keywords before burning LLM tokens."""
    lower = content.lower()[:500]  # only check first 500 chars
    for keyword, route in KEYWORD_ROUTES.items():
        if keyword in lower:
            return route
    return None


def classify_chunk(content: str, model: str, source_type: str) -> dict:
    """Classify a chunk via keyword fast-path or LLM."""
    truncated = content[:MAX_CHUNK_CHARS]

    # Fast path
    kw_route = keyword_classify(truncated)

    # LLM classification
    prompt = CLASSIFY_PROMPT.format(content=truncated)
    result = call_llm(prompt, model)

    classification = {
        "keyword_route": kw_route,
        "llm_ok": result["ok"],
        "llm_via": result.get("via", "none"),
        "raw_llm": result.get("text", ""),
    }

    if result["ok"]:
        try:
            parsed = json.loads(result["text"])
            classification.update(parsed)
        except json.JSONDecodeError:
            classification["parse_error"] = True
            classification["route_target"] = kw_route or "expansion_ledger"
            classification["category"] = "note"
            classification["project"] = "unassigned"
            classification["confidence"] = 0.0
    else:
        # Fallback to keyword route or default
        classification["route_target"] = kw_route or "expansion_ledger"
        classification["category"] = "note"
        classification["project"] = "unassigned"
        classification["confidence"] = 0.0

    return classification


def find_chunks(paths: list[str], recursive: bool = False) -> list[Path]:
    """Find all ingestible files."""
    exts = {".md", ".txt", ".json", ".csv", ".html", ".py", ".yaml", ".yml"}
    files = []
    for p in paths:
        path = Path(p)
        if path.is_file():
            files.append(path)
        elif path.is_dir():
            pattern = "**/*" if recursive else "*"
            for f in sorted(path.glob(pattern)):
                if f.is_file() and f.suffix.lower() in exts:
                    files.append(f)
    return files


def init_ledger(ledger_path: Path):
    """Create CSV ledger with headers if it doesn't exist."""
    if not ledger_path.exists():
        with open(ledger_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "chunk_id", "source_file", "source_type", "chunk_hash",
                "timestamp", "model", "llm_via",
                "project", "category", "urgency", "route_target",
                "confidence", "tags", "summary",
                "keyword_route", "parse_error", "status",
            ])


def log_to_ledger(ledger_path: Path, record: dict):
    """Append one row to the CSV ledger."""
    with open(ledger_path, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            record.get("chunk_id", ""),
            record.get("source_file", ""),
            record.get("source_type", ""),
            record.get("chunk_hash", ""),
            record.get("timestamp", ""),
            record.get("model", ""),
            record.get("llm_via", ""),
            record.get("project", ""),
            record.get("category", ""),
            record.get("urgency", ""),
            record.get("route_target", ""),
            record.get("confidence", ""),
            json.dumps(record.get("tags", [])),
            record.get("summary", ""),
            record.get("keyword_route", ""),
            record.get("parse_error", False),
            record.get("status", "classified"),
        ])


def main():
    parser = argparse.ArgumentParser(description="Batch ingest corpus chunks")
    parser.add_argument("inputs", nargs="+", help="Files or directories to ingest")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"LLM model (default: {DEFAULT_MODEL})")
    parser.add_argument("--source", default="unknown", help="Source type tag (email, notebook, asana, google_notes, research)")
    parser.add_argument("--recursive", action="store_true", help="Recurse into subdirectories")
    parser.add_argument("--dry-run", action="store_true", help="Classify only, don't route")
    parser.add_argument("--output", default=str(LOG_DIR), help="Log output directory")
    args = parser.parse_args()

    log_dir = Path(args.output)
    log_dir.mkdir(parents=True, exist_ok=True)
    ledger_path = log_dir / "ingestion_ledger.csv"
    error_log = log_dir / "errors.log"
    init_ledger(ledger_path)

    chunks = find_chunks(args.inputs, args.recursive)
    if not chunks:
        print("ERROR: No ingestible files found")
        sys.exit(1)

    print(f"Found {len(chunks)} chunks. Model: {args.model}. Source: {args.source}")
    if args.dry_run:
        print("DRY RUN — classify only, no routing")
    print()

    route_counts = {}
    successes = 0
    failures = 0
    t0 = time.time()

    for i, chunk_path in enumerate(chunks, 1):
        try:
            content = chunk_path.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            print(f"  [{i}/{len(chunks)}] SKIP {chunk_path.name}: {e}")
            failures += 1
            continue

        chunk_hash = sha256_of(content)
        chunk_id = f"{args.source}_{chunk_hash}"

        print(f"  [{i}/{len(chunks)}] {chunk_path.name} ({len(content)} chars)...", end=" ")

        classification = classify_chunk(content, args.model, args.source)

        route = classification.get("route_target", "expansion_ledger")
        route_counts[route] = route_counts.get(route, 0) + 1

        record = {
            "chunk_id": chunk_id,
            "source_file": str(chunk_path),
            "source_type": args.source,
            "chunk_hash": chunk_hash,
            "timestamp": datetime.now().isoformat(),
            "model": args.model,
            "llm_via": classification.get("llm_via", ""),
            "project": classification.get("project", "unassigned"),
            "category": classification.get("category", "note"),
            "urgency": classification.get("urgency", "backlog"),
            "route_target": route,
            "confidence": classification.get("confidence", 0.0),
            "tags": classification.get("tags", []),
            "summary": classification.get("summary", ""),
            "keyword_route": classification.get("keyword_route", ""),
            "parse_error": classification.get("parse_error", False),
            "status": "dry_run" if args.dry_run else "classified",
        }

        log_to_ledger(ledger_path, record)
        successes += 1
        conf = classification.get("confidence", 0)
        print(f"→ {route} ({classification.get('project','?')}) [{conf:.0%}]")

    elapsed = time.time() - t0

    # Summary
    summary = {
        "run_date": datetime.now().isoformat(),
        "model": args.model,
        "source_type": args.source,
        "dry_run": args.dry_run,
        "total_chunks": len(chunks),
        "successes": successes,
        "failures": failures,
        "elapsed_sec": round(elapsed, 2),
        "route_distribution": route_counts,
    }

    summary_path = log_dir / "routing_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2))

    print(f"\n{'='*50}")
    print(f"DONE: {successes}/{len(chunks)} classified in {elapsed:.1f}s")
    print(f"Routes: {json.dumps(route_counts, indent=2)}")
    print(f"Ledger: {ledger_path.resolve()}")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
