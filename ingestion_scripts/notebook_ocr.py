#!/usr/bin/env python3
"""notebook_ocr.py — Notebook page transcription via local vision model.

Sends photos to Ollama's vision-capable model, returns structured text
with color annotations. Designed to stress-test the pipeline so errors
can be cataloged and corrected.

Usage:
    python notebook_ocr.py <image_path_or_directory> [--model llava:13b] [--output-dir ./transcripts]

Outputs per image:
    - <basename>_transcript.md   (clean text with [COLOR] tags)
    - <basename>_raw.json        (full model response for debugging)
    - <basename>_errors.log      (flagged low-confidence sections)
"""

import argparse
import base64
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

try:
    import httpx
except ImportError:
    print("Installing httpx...")
    os.system(f"{sys.executable} -m pip install httpx --break-system-packages -q")
    import httpx


OLLAMA_BASE = os.environ.get("OLLAMA_HOST", "http://localhost:11434")

SYSTEM_PROMPT = """You are a precise handwriting transcription system. Your job:

1. Transcribe the handwritten text on this notebook page EXACTLY as written.
2. Preserve line breaks where they appear on the page.
3. For each line or segment, note the ink color if distinguishable. Use these tags:
   [BLACK], [BLUE], [RED], [GREEN], [PURPLE], [ORANGE], [BROWN], [PENCIL]
   If you cannot determine the color, use [UNK_COLOR].
   Place the tag at the START of each line or color-change boundary.
4. If a word or phrase is illegible, write [ILLEGIBLE: best_guess] with your best attempt.
5. If you see diagrams, arrows, or non-text marks, describe them in [DIAGRAM: description].
6. If you see numbered or bulleted lists, preserve the structure.
7. If you see underlines, circles, or emphasis marks, note them: [UNDERLINED], [CIRCLED], [STARRED].

Output ONLY the transcription. No commentary, no headers, no preamble.
"""

LEGEND_PROMPT = """This is a notebook legend page showing a color-coding system.
For each color shown, extract:
- The color name
- What that color means/represents in this system
- Any symbols or shorthand associated with it

Output as a structured list:
COLOR: <color> | MEANING: <meaning> | SYMBOLS: <any symbols or none>
"""


def encode_image(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def check_ollama_ready(model: str) -> bool:
    try:
        r = httpx.get(f"{OLLAMA_BASE}/api/tags", timeout=10)
        if r.status_code != 200:
            print(f"ERROR: Ollama returned status {r.status_code}")
            return False
        models = [m["name"] for m in r.json().get("models", [])]
        base_model = model.split(":")[0]
        found = any(model in m or base_model in m for m in models)
        if not found:
            print(f"ERROR: Model '{model}' not found. Available: {models}")
            print(f"  Run: ollama pull {model}")
            return False
        print(f"OK: Ollama running, model '{model}' available")
        return True
    except httpx.ConnectError:
        print(f"ERROR: Cannot connect to Ollama at {OLLAMA_BASE}")
        return False


def transcribe_page(image_path: str, model: str, is_legend: bool = False) -> dict:
    prompt = LEGEND_PROMPT if is_legend else SYSTEM_PROMPT
    img_b64 = encode_image(image_path)
    payload = {
        "model": model,
        "prompt": prompt,
        "images": [img_b64],
        "stream": False,
        "options": {"temperature": 0.1, "num_predict": 4096},
    }
    start = time.time()
    try:
        r = httpx.post(f"{OLLAMA_BASE}/api/generate", json=payload, timeout=300)
        elapsed = time.time() - start
        if r.status_code != 200:
            return {"success": False, "error": f"HTTP {r.status_code}: {r.text[:500]}", "elapsed_sec": elapsed}
        data = r.json()
        return {
            "success": True,
            "transcript": data.get("response", ""),
            "model": data.get("model", model),
            "elapsed_sec": elapsed,
            "eval_count": data.get("eval_count", 0),
        }
    except httpx.TimeoutException:
        return {"success": False, "error": "Timeout after 300s", "elapsed_sec": time.time() - start}
    except Exception as e:
        return {"success": False, "error": str(e), "elapsed_sec": time.time() - start}


def extract_errors(transcript: str) -> list[str]:
    errors = []
    for i, line in enumerate(transcript.splitlines(), 1):
        if "[ILLEGIBLE" in line:
            errors.append(f"Line {i}: {line.strip()}")
        if "[UNK_COLOR]" in line:
            errors.append(f"Line {i}: Unknown color — {line.strip()}")
    return errors


def process_image(image_path: str, model: str, output_dir: str, is_legend: bool = False):
    basename = Path(image_path).stem
    suffix = "_legend" if is_legend else ""
    print(f"\n{'='*60}\nProcessing: {image_path}\n{'='*60}")
    result = transcribe_page(image_path, model, is_legend)
    raw_path = os.path.join(output_dir, f"{basename}{suffix}_raw.json")
    with open(raw_path, "w") as f:
        json.dump({"source_image": str(image_path), "timestamp": datetime.now().isoformat(), **result}, f, indent=2)
    if not result["success"]:
        print(f"  FAILED: {result['error']}")
        return result
    transcript = result["transcript"]
    md_path = os.path.join(output_dir, f"{basename}{suffix}_transcript.md")
    with open(md_path, "w") as f:
        f.write(f"<!-- Source: {image_path} | Model: {result['model']} | {datetime.now().isoformat()} | {result['elapsed_sec']:.1f}s -->\n\n")
        f.write(transcript)
    errors = extract_errors(transcript)
    err_path = os.path.join(output_dir, f"{basename}{suffix}_errors.log")
    with open(err_path, "w") as f:
        f.write(f"# {len(errors)} flagged items for {image_path}\n\n" if errors else "# No flagged items\n")
        for e in errors:
            f.write(f"{e}\n")
    lines = transcript.splitlines()
    print(f"  OK — {len(lines)} lines, {len(errors)} flagged, {result['elapsed_sec']:.1f}s")
    return result


def main():
    parser = argparse.ArgumentParser(description="Transcribe notebook pages via Ollama vision model")
    parser.add_argument("input", help="Image file or directory of images")
    parser.add_argument("--model", default="llava:13b", help="Ollama vision model")
    parser.add_argument("--output-dir", default="./transcripts", help="Output directory")
    parser.add_argument("--legend", action="store_true", help="Treat as color legend page")
    args = parser.parse_args()
    os.makedirs(args.output_dir, exist_ok=True)
    if not check_ollama_ready(args.model):
        sys.exit(1)
    input_path = Path(args.input)
    if input_path.is_file():
        images = [str(input_path)]
    elif input_path.is_dir():
        exts = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".heic"}
        images = sorted(str(p) for p in input_path.iterdir() if p.suffix.lower() in exts)
        if not images:
            print(f"No images found in {input_path}")
            sys.exit(1)
        print(f"Found {len(images)} images")
    else:
        print(f"Not found: {args.input}")
        sys.exit(1)
    summary = {"total": len(images), "success": 0, "failed": 0, "total_errors": 0, "total_time": 0}
    for img in images:
        result = process_image(img, args.model, args.output_dir, args.legend)
        if result["success"]:
            summary["success"] += 1
            summary["total_time"] += result["elapsed_sec"]
            summary["total_errors"] += len(extract_errors(result.get("transcript", "")))
        else:
            summary["failed"] += 1
    print(f"\n{'='*60}\nBATCH: {summary['success']}/{summary['total']} OK, {summary['total_errors']} flagged, {summary['total_time']:.1f}s total\n{'='*60}")
    with open(os.path.join(args.output_dir, "BATCH_SUMMARY.json"), "w") as f:
        json.dump({**summary, "timestamp": datetime.now().isoformat(), "model": args.model}, f, indent=2)


if __name__ == "__main__":
    main()
