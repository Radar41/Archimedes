# Archimedes Ingestion Scripts — April 7, 2026

## Quick Start

```bash
# 1. Copy to HP
scp -r ingestion_scripts/ radar41@<hp-ip>:~/ingestion_scripts/

# 2. Preflight
bash preflight_check.sh

# 3. Pull vision model if missing
ollama pull llava:13b

# 4. Transcribe notebook photos
python3 notebook_ocr.py /path/to/photos/ --output-dir ~/transcripts

# 5. Legend page specifically
python3 notebook_ocr.py legend.jpg --legend --output-dir ~/transcripts

# 6. Voice pipe (optional)
chmod +x voice_pipe.sh
./voice_pipe.sh --interactive
```

## Scripts
- preflight_check.sh — system readiness verification
- notebook_ocr.py — vision model transcription with color tags
- voice_pipe.sh — voice cleanup + keyword routing via Ollama

## NOT covered here (separate/pending)
- Email corpus parsers (waiting on conversations.json export)
- Asana project JSON export
- Google notes export
- IntakeNormalize downstream pipeline
