#!/usr/bin/env bash
# preflight_check.sh — Pre-ingestion readiness check
set -uo pipefail
OLLAMA_HOST="${OLLAMA_HOST:-http://localhost:11434}"
VISION_MODEL="${VISION_MODEL:-llava:13b}"
PASS=0; FAIL=0; WARN=0
check() {
    case "$2" in
        PASS) echo "  ✅ $1 — $3"; ((PASS++)) ;;
        FAIL) echo "  ❌ $1 — $3"; ((FAIL++)) ;;
        WARN) echo "  ⚠️  $1 — $3"; ((WARN++)) ;;
    esac
}
echo "═══ ARCHIMEDES INGESTION PREFLIGHT — $(date) ═══"
echo ""
echo "1. OLLAMA"
if curl -s "$OLLAMA_HOST/api/tags" > /tmp/ollama_tags.json 2>/dev/null; then
    check "Ollama" "PASS" "reachable"
    if jq -e ".models[] | select(.name | contains(\"${VISION_MODEL%%:*}\"))" /tmp/ollama_tags.json > /dev/null 2>&1; then
        check "Vision model ($VISION_MODEL)" "PASS" "available"
    else
        check "Vision model ($VISION_MODEL)" "FAIL" "MISSING — run: ollama pull $VISION_MODEL"
    fi
else
    check "Ollama" "FAIL" "not reachable at $OLLAMA_HOST"
fi
echo ""
echo "2. DOCKER"
if command -v docker &>/dev/null; then
    running=$(docker ps --format '{{.Names}}' 2>/dev/null | sort)
    [ -n "$running" ] && check "Docker" "PASS" "$(echo "$running" | wc -l) containers" || check "Docker" "FAIL" "no containers running"
    for svc in postgres temporal minio langfuse litellm; do
        echo "$running" | grep -qi "$svc" && check "  $svc" "PASS" "up" || check "  $svc" "WARN" "not found"
    done
else check "Docker" "FAIL" "not installed"; fi
echo ""
echo "3. DISK"
avail=$(df -BG ~ 2>/dev/null | tail -1 | awk '{print $4}' | tr -d 'G')
[ "${avail:-0}" -gt 10 ] && check "Space" "PASS" "${avail}G free" || check "Space" "WARN" "${avail:-?}G free"
echo ""
echo "4. SCRIPTS"
SD="$(cd "$(dirname "$0")" && pwd)"
for s in notebook_ocr.py voice_pipe.sh; do [ -f "$SD/$s" ] && check "$s" "PASS" "present" || check "$s" "FAIL" "MISSING"; done
echo ""
echo "═══ PASS:$PASS FAIL:$FAIL WARN:$WARN ═══"
[ "$FAIL" -eq 0 ] && echo "✅ READY" || echo "❌ $FAIL BLOCKERS"
rm -f /tmp/ollama_tags.json; exit "$FAIL"
