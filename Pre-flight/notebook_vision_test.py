#!/usr/bin/env python3
"""
notebook_vision_test.py — Stress-test local vision model on handwritten notebook pages.

PURPOSE: Find where the model fails BEFORE the 1:30 studio session.
Run this on HP (node_hp) where Ollama is installed.

USAGE:
  python3 notebook_vision_test.py /path/to/photos/          # process all images in dir
  python3 notebook_vision_test.py photo1.jpg photo2.png      # specific files
  python3 notebook_vision_test.py --model llava:13b photo.jpg # override model

PREREQUISITES:
  - Ollama running: `ollama serve` or systemd service
  - Vision model pulled: `ollama pull llava` (or llava:13b, bakllava, llava-llama3)
  - pip install requests Pillow (Pillow optional, for image validation)

OUTPUT:
  ./notebook_ocr_results/
    notebook_p001_transcript.md    # raw model output
    notebook_p001_errors.md        # empty if clean; fill in corrections manually
    notebook_legend.md             # generated if --legend flag on first page
    run_summary.json               # timing, model, token counts, error flags
"""

import argparse
import base64
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

# ── Config ──────────────────────────────────────────────────
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
DEFAULT_MODEL = os.getenv("OLLAMA_VISION_MODEL", "llava")
OUTPUT_DIR = Path("./notebook_ocr_results")

# ── Prompts ─────────────────────────────────────────────────

TRANSCRIPTION_PROMPT = """You are transcribing a handwritten notebook page. Follow these rules exactly:

1. Transcribe EVERY word you can read, preserving line breaks and structure.
2. For words you cannot read, write [ILLEGIBLE] in place.
3. For words you're uncertain about, write [UNCERTAIN: best_guess] in place.
4. Note ink/pen color where distinguishable. Prefix lines or sections with color tags:
   [BLACK], [BLUE], [RED], [GREEN], [PURPLE], [ORANGE], [BROWN], [PENCIL/GRAY]
   If color is unclear or uniform, use [BLACK] as default.
5. Preserve any diagrams, arrows, or annotations as text descriptions in [DIAGRAM: description].
6. Preserve numbering, bullet points, indentation, and any structural formatting.
7. If there are margin notes, prefix them with [MARGIN:].
8. Do NOT interpret, summarize, or reorganize. Transcribe exactly as written.

Output the transcription only. No preamble, no commentary."""

LEGEND_PROMPT = """This notebook page contains a color-coding legend/key that defines what each ink color means.

1. Identify each color used and what category/meaning it represents.
2. Output a structured legend in this format:

COLOR_CODE | COLOR_NAME | MEANING | NOTES
e.g.:
RED | Red ink | Urgent / Blockers | Items requiring immediate attention
BLUE | Blue ink | Questions / Open items | Unresolved questions for later

List ALL colors you can identify with their meanings. If a color's meaning is unclear, write [UNCLEAR] in the meaning field."""

COLOR_ANALYSIS_PROMPT = """Analyze this notebook page for color usage. For each distinct ink/pen color visible:
1. Name the color
2. Count approximate number of lines/items in that color
3. Note if color seems to correlate with content type (e.g., all red items are tasks, all blue are questions)

Output as a simple list. This is for calibration — be honest about what you can and cannot distinguish."""


def check_ollama(model: str) -> bool:
    """Verify Ollama is running and model is available."""
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        r.raise_for_status()
        models = [m["name"] for m in r.json().get("models", [])]
        if not models:
            print("WARNING: No models found in Ollama. Pull one: ollama pull llava")
            return False
        # Check for exact match or prefix match
        found = any(model in m or m.startswith(model) for m in models)
        if not found:
            print(f"WARNING: Model '{model}' not found. Available: {', '.join(models)}")
            print(f"Pull it with: ollama pull {model}")
            return False
        print(f"OK: Ollama running, model '{model}' available")
        return True
    except requests.ConnectionError:
        print(f"ERROR: Cannot connect to Ollama at {OLLAMA_URL}")
        print("Start it with: ollama serve")
        return False


def encode_image(path: Path) -> str:
    """Read and base64-encode an image file."""
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def call_vision(model: str, prompt: str, image_b64: str, timeout: int = 120) -> dict:
    """Send image + prompt to Ollama vision API. Returns dict with response and timing."""
    payload = {
        "model": model,
        "prompt": prompt,
        "images": [image_b64],
        "stream": False,
        "options": {
            "temperature": 0.1,  # low temp for faithful transcription
            "num_predict": 4096,
        },
    }
    t0 = time.time()
    try:
        r = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json=payload,
            timeout=timeout,
        )
        r.raise_for_status()
        elapsed = time.time() - t0
        data = r.json()
        return {
            "ok": True,
            "text": data.get("response", ""),
            "elapsed_sec": round(elapsed, 2),
            "eval_count": data.get("eval_count", 0),
            "prompt_eval_count": data.get("prompt_eval_count", 0),
            "model": data.get("model", model),
        }
    except requests.Timeout:
        return {"ok": False, "text": "", "error": f"Timeout after {timeout}s", "elapsed_sec": timeout}
    except Exception as e:
        return {"ok": False, "text": "", "error": str(e), "elapsed_sec": time.time() - t0}


def process_page(
    image_path: Path,
    model: str,
    page_num: int,
    is_legend: bool = False,
    do_color_analysis: bool = True,
) -> dict:
    """Process a single notebook page. Returns result dict."""
    print(f"\n{'='*60}")
    print(f"Page {page_num:03d}: {image_path.name}")
    print(f"{'='*60}")

    img_b64 = encode_image(image_path)
    file_size_kb = image_path.stat().st_size / 1024
    print(f"  Image size: {file_size_kb:.0f} KB")

    results = {
        "page_num": page_num,
        "source_file": str(image_path),
        "file_size_kb": round(file_size_kb, 1),
        "timestamp": datetime.now().isoformat(),
    }

    # ── Primary transcription ───────────────────────────────
    prompt = LEGEND_PROMPT if is_legend else TRANSCRIPTION_PROMPT
    print(f"  Running {'legend extraction' if is_legend else 'transcription'}...")
    tx = call_vision(model, prompt, img_b64)
    results["transcription"] = tx

    if tx["ok"]:
        print(f"  OK: {len(tx['text'])} chars in {tx['elapsed_sec']}s")

        # Save transcript
        prefix = "notebook_legend" if is_legend else f"notebook_p{page_num:03d}_transcript"
        out_path = OUTPUT_DIR / f"{prefix}.md"
        header = f"<!-- source: {image_path.name} | model: {tx.get('model',model)} | date: {results['timestamp']} -->\n\n"
        out_path.write_text(header + tx["text"], encoding="utf-8")
        print(f"  Saved: {out_path}")

        # Create empty error file for manual correction
        err_path = OUTPUT_DIR / f"notebook_p{page_num:03d}_errors.md"
        err_path.write_text(
            f"# Corrections for page {page_num:03d} ({image_path.name})\n\n"
            "<!-- Fill in corrections below. Format: -->\n"
            "<!-- LINE N: model said 'X' → should be 'Y' -->\n"
            "<!-- COLOR: model said [BLACK] → should be [RED] -->\n\n",
            encoding="utf-8",
        )
    else:
        print(f"  FAILED: {tx.get('error', 'unknown')}")

    # ── Color analysis pass (separate from transcription) ───
    if do_color_analysis and not is_legend:
        print(f"  Running color analysis...")
        ca = call_vision(model, COLOR_ANALYSIS_PROMPT, img_b64, timeout=60)
        results["color_analysis"] = ca
        if ca["ok"]:
            ca_path = OUTPUT_DIR / f"notebook_p{page_num:03d}_colors.md"
            ca_path.write_text(ca["text"], encoding="utf-8")
            print(f"  Color analysis: {len(ca['text'])} chars in {ca['elapsed_sec']}s")
        else:
            print(f"  Color analysis failed: {ca.get('error')}")

    return results


def find_images(paths: list[str]) -> list[Path]:
    """Resolve input paths to image files."""
    exts = {".jpg", ".jpeg", ".png", ".heic", ".webp", ".bmp", ".tiff", ".tif"}
    images = []
    for p in paths:
        path = Path(p)
        if path.is_dir():
            for f in sorted(path.iterdir()):
                if f.suffix.lower() in exts:
                    images.append(f)
        elif path.is_file() and path.suffix.lower() in exts:
            images.append(path)
        else:
            print(f"WARNING: Skipping {p} (not an image or directory)")
    return images


def main():
    parser = argparse.ArgumentParser(description="Test vision model OCR on notebook pages")
    parser.add_argument("inputs", nargs="+", help="Image files or directories")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Ollama vision model (default: {DEFAULT_MODEL})")
    parser.add_argument("--legend", type=int, default=None, help="Page number (1-indexed) that contains the color legend")
    parser.add_argument("--no-color", action="store_true", help="Skip separate color analysis pass")
    parser.add_argument("--output", default=str(OUTPUT_DIR), help="Output directory")
    args = parser.parse_args()

    global OUTPUT_DIR
    OUTPUT_DIR = Path(args.output)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Preflight
    if not check_ollama(args.model):
        sys.exit(1)

    images = find_images(args.inputs)
    if not images:
        print("ERROR: No images found")
        sys.exit(1)

    print(f"\nFound {len(images)} images. Model: {args.model}")
    print(f"Output: {OUTPUT_DIR.resolve()}\n")

    # Process
    run_results = []
    total_t0 = time.time()

    for i, img in enumerate(images, 1):
        is_legend = (args.legend == i)
        result = process_page(img, args.model, i, is_legend=is_legend, do_color_analysis=not args.no_color)
        run_results.append(result)

    total_elapsed = time.time() - total_t0

    # Summary
    summary = {
        "run_date": datetime.now().isoformat(),
        "model": args.model,
        "total_pages": len(images),
        "total_elapsed_sec": round(total_elapsed, 2),
        "avg_sec_per_page": round(total_elapsed / len(images), 2) if images else 0,
        "successes": sum(1 for r in run_results if r["transcription"]["ok"]),
        "failures": sum(1 for r in run_results if not r["transcription"]["ok"]),
        "pages": run_results,
    }

    summary_path = OUTPUT_DIR / "run_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(f"\n{'='*60}")
    print(f"DONE: {summary['successes']}/{summary['total_pages']} pages transcribed")
    print(f"Time: {summary['total_elapsed_sec']}s total, {summary['avg_sec_per_page']}s/page avg")
    print(f"Failures: {summary['failures']}")
    print(f"Results: {OUTPUT_DIR.resolve()}")
    print(f"{'='*60}")

    if summary["failures"] > 0:
        print("\nFailed pages:")
        for r in run_results:
            if not r["transcription"]["ok"]:
                print(f"  Page {r['page_num']}: {r['transcription'].get('error')}")


if __name__ == "__main__":
    main()
