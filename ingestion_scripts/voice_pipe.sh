#!/usr/bin/env bash
# voice_pipe.sh — Voice-to-text cleanup and routing via local Ollama
# Usage: echo "text" | ./voice_pipe.sh  OR  ./voice_pipe.sh "text"  OR  ./voice_pipe.sh --interactive
# Routes: note→notes.md, task→tasks_queue.md, code→code_notes.md, thought→expansion_ledger.md, other→inbox.md

set -euo pipefail
OLLAMA_HOST="${OLLAMA_HOST:-http://localhost:11434}"
OLLAMA_MODEL="${OLLAMA_MODEL:-mistral}"
OUTPUT_DIR="${VOICE_PIPE_DIR:-$HOME/voice_capture}"
ACTIVE_TASK="${ACTIVE_TASK:-unset}"
TIMESTAMP=$(date +%Y%m%dT%H%M%S)
mkdir -p "$OUTPUT_DIR"

cleanup_text() {
    local raw="$1"
    local prompt="Clean up this voice-dictated text. Remove filler words (um, uh, like, you know), fix speech-to-text errors, add punctuation, DO NOT change meaning. Return ONLY cleaned text.\n\nActive task: $ACTIVE_TASK\n\nRaw:\n$raw"
    local response
    response=$(curl -s "$OLLAMA_HOST/api/generate" \
        -d "$(jq -n --arg model "$OLLAMA_MODEL" --arg prompt "$prompt" \
            '{model: $model, prompt: $prompt, stream: false, options: {temperature: 0.1}}')" 2>/dev/null)
    echo "$response" | jq -r '.response // empty' 2>/dev/null || echo "$raw"
}

route_text() {
    local cleaned="$1"
    local first_word
    first_word=$(echo "$cleaned" | awk '{print tolower($1)}')
    local target category
    case "$first_word" in
        note|notes)   target="$OUTPUT_DIR/notes.md"; category="NOTE"; cleaned=$(echo "$cleaned" | sed 's/^[Nn]otes\?\s*//') ;;
        task|tasks)   target="$OUTPUT_DIR/tasks_queue.md"; category="TASK"; cleaned=$(echo "$cleaned" | sed 's/^[Tt]asks\?\s*//') ;;
        code)         target="$OUTPUT_DIR/code_notes.md"; category="CODE"; cleaned=$(echo "$cleaned" | sed 's/^[Cc]ode\s*//') ;;
        thought*|idea) target="$OUTPUT_DIR/expansion_ledger.md"; category="THOUGHT"; cleaned=$(echo "$cleaned" | sed 's/^[Tt]houghts\?\s*//;s/^[Ii]dea\s*//') ;;
        *)            target="$OUTPUT_DIR/inbox.md"; category="INBOX" ;;
    esac
    printf "\n---\n<!-- [%s] %s | task: %s -->\n%s\n" "$category" "$TIMESTAMP" "$ACTIVE_TASK" "$cleaned" >> "$target"
    echo "✓ [$category] → $(basename "$target"): $cleaned"
    echo "$TIMESTAMP|$ACTIVE_TASK|$cleaned" >> "$OUTPUT_DIR/capture_log.csv"
}

process_input() {
    local raw="$1"
    [ -z "$raw" ] && return
    echo "⏳ Cleaning..."
    local cleaned
    cleaned=$(cleanup_text "$raw")
    [ -z "$cleaned" ] && cleaned="$raw"
    route_text "$cleaned"
}

if [ "${1:-}" = "--interactive" ]; then
    echo "Voice pipe interactive. Routing: note/task/code/thought → target, other → inbox. Ctrl+C to quit."
    while IFS= read -r -p "> " line; do process_input "$line"; done
elif [ -n "${1:-}" ]; then
    process_input "$*"
elif [ ! -t 0 ]; then
    while IFS= read -r line; do process_input "$line"; done
else
    echo "Usage: voice_pipe.sh <text> | --interactive | pipe"
    exit 1
fi
