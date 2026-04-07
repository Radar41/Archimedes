#!/usr/bin/env bash
# voice_pipe.sh — Voice-to-text cleanup and routing via local Ollama
#
# Usage:
#   echo "some dictated text" | ./voice_pipe.sh
#   ./voice_pipe.sh "some dictated text"
#   ./voice_pipe.sh --interactive   (continuous mode)
#
# Routes based on first keyword:
#   note  → appends to notes.md (→ Obsidian)
#   task  → appends to tasks_queue.md (→ Asana via sync adapter)
#   code  → appends to code_notes.md (→ GitHub)
#   thought → appends to expansion_ledger.md (→ adjacent queue)
#   (no keyword) → appends to inbox.md (→ manual triage)

set -euo pipefail

OLLAMA_HOST="${OLLAMA_HOST:-http://localhost:11434}"
OLLAMA_MODEL="${OLLAMA_MODEL:-mistral}"
OUTPUT_DIR="${VOICE_PIPE_DIR:-$HOME/voice_capture}"
ACTIVE_TASK="${ACTIVE_TASK:-unset}"
TIMESTAMP=$(date +%Y%m%dT%H%M%S)

mkdir -p "$OUTPUT_DIR"

# ── Ollama cleanup ──────────────────────────────────────
cleanup_text() {
    local raw="$1"
    local prompt="Clean up this voice-dictated text. Remove filler words (um, uh, like, you know), fix obvious speech-to-text errors, add punctuation, but DO NOT change the meaning or add information. If the text references a task context, preserve it. Return ONLY the cleaned text, nothing else.

Active task context: $ACTIVE_TASK

Raw input:
$raw"

    local response
    response=$(curl -s "$OLLAMA_HOST/api/generate" \
        -d "$(jq -n --arg model "$OLLAMA_MODEL" --arg prompt "$prompt" \
            '{model: $model, prompt: $prompt, stream: false, options: {temperature: 0.1}}')" \
        2>/dev/null)

    echo "$response" | jq -r '.response // empty' 2>/dev/null || echo "$raw"
}

# ── Routing ─────────────────────────────────────────────
route_text() {
    local cleaned="$1"
    local first_word
    first_word=$(echo "$cleaned" | awk '{print tolower($1)}')

    local target
    local category
    case "$first_word" in
        note|notes)
            target="$OUTPUT_DIR/notes.md"
            category="NOTE"
            # Strip the routing keyword from the content
            cleaned=$(echo "$cleaned" | sed 's/^[Nn]otes\?\s*//')
            ;;
        task|tasks)
            target="$OUTPUT_DIR/tasks_queue.md"
            category="TASK"
            cleaned=$(echo "$cleaned" | sed 's/^[Tt]asks\?\s*//')
            ;;
        code)
            target="$OUTPUT_DIR/code_notes.md"
            category="CODE"
            cleaned=$(echo "$cleaned" | sed 's/^[Cc]ode\s*//')
            ;;
        thought|thoughts|idea)
            target="$OUTPUT_DIR/expansion_ledger.md"
            category="THOUGHT"
            cleaned=$(echo "$cleaned" | sed 's/^[Tt]houghts\?\s*//;s/^[Ii]dea\s*//')
            ;;
        *)
            target="$OUTPUT_DIR/inbox.md"
            category="INBOX"
            ;;
    esac

    # Append with metadata
    {
        echo ""
        echo "---"
        echo "<!-- [$category] $TIMESTAMP | task: $ACTIVE_TASK -->"
        echo "$cleaned"
    } >> "$target"

    echo "✓ [$category] → $(basename "$target")"
    echo "  $cleaned"
}

# ── Main ────────────────────────────────────────────────
process_input() {
    local raw="$1"
    if [ -z "$raw" ]; then
        return
    fi

    echo "⏳ Cleaning..."
    local cleaned
    cleaned=$(cleanup_text "$raw")

    if [ -z "$cleaned" ]; then
        echo "⚠ Ollama returned empty — using raw input"
        cleaned="$raw"
    fi

    route_text "$cleaned"

    # Log to master capture file
    echo "$TIMESTAMP|$ACTIVE_TASK|$raw|$cleaned" >> "$OUTPUT_DIR/capture_log.csv"
}

# ── Entry points ────────────────────────────────────────
if [ "${1:-}" = "--interactive" ]; then
    echo "Voice pipe interactive mode. Type or paste, press Enter. Ctrl+C to quit."
    echo "Routing: note/task/code/thought → target file, other → inbox"
    echo "Active task: $ACTIVE_TASK"
    echo "Output dir: $OUTPUT_DIR"
    echo "---"
    while IFS= read -r -p "> " line; do
        process_input "$line"
    done
elif [ -n "${1:-}" ]; then
    process_input "$*"
elif [ ! -t 0 ]; then
    # Piped input
    while IFS= read -r line; do
        process_input "$line"
    done
else
    echo "Usage: voice_pipe.sh <text> | voice_pipe.sh --interactive | echo text | voice_pipe.sh"
    exit 1
fi
