#!/usr/bin/env bash
# preflight_check.sh — Run before the 1:30 ingestion session
# Verifies: Ollama, vision model, Docker stack, disk space, scripts present
# Usage: bash preflight_check.sh

set -uo pipefail

OLLAMA_HOST="${OLLAMA_HOST:-http://localhost:11434}"
VISION_MODEL="${VISION_MODEL:-llava:13b}"
CLEANUP_MODEL="${CLEANUP_MODEL:-mistral}"

PASS=0; FAIL=0; WARN=0

check() {
    local label="$1" status="$2" detail="$3"
    case "$status" in
        PASS) echo "  ✅ $label — $detail"; ((PASS++)) ;;
        FAIL) echo "  ❌ $label — $detail"; ((FAIL++)) ;;
        WARN) echo "  ⚠️  $label — $detail"; ((WARN++)) ;;
    esac
}

echo "╔══════════════════════════════════════════════════════╗"
echo "║  ARCHIMEDES INGESTION — PREFLIGHT CHECK             ║"
echo "║  $(date '+%Y-%m-%d %H:%M:%S')                          ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""

# ── 1. OLLAMA ───────────────────────────────────────────
echo "1. OLLAMA STATUS"
if curl -s "$OLLAMA_HOST/api/tags" > /tmp/ollama_tags.json 2>/dev/null; then
    check "Ollama reachable" "PASS" "$OLLAMA_HOST"
    if jq -e ".models[] | select(.name | contains(\"${VISION_MODEL%%:*}\"))" /tmp/ollama_tags.json > /dev/null 2>&1; then
        check "Vision model ($VISION_MODEL)" "PASS" "available"
    else
        check "Vision model ($VISION_MODEL)" "FAIL" "NOT PULLED — run: ollama pull $VISION_MODEL"
    fi
    if jq -e ".models[] | select(.name | contains(\"${CLEANUP_MODEL%%:*}\"))" /tmp/ollama_tags.json > /dev/null 2>&1; then
        check "Cleanup model ($CLEANUP_MODEL)" "PASS" "available"
    else
        check "Cleanup model ($CLEANUP_MODEL)" "WARN" "not pulled — voice pipe will pass raw text"
    fi
else
    check "Ollama reachable" "FAIL" "cannot connect to $OLLAMA_HOST — run: ollama serve"
    check "Vision model" "FAIL" "skipped"
    check "Cleanup model" "FAIL" "skipped"
fi
echo ""

# ── 2. DOCKER STACK ─────────────────────────────────────
echo "2. DOCKER STACK"
if command -v docker &> /dev/null; then
    check "Docker installed" "PASS" "$(docker --version 2>/dev/null | head -1)"
    running=$(docker ps --format '{{.Names}}' 2>/dev/null | sort)
    if [ -n "$running" ]; then
        count=$(echo "$running" | wc -l)
        check "Containers running" "PASS" "$count containers"
        for svc in postgres temporal minio langfuse litellm; do
            if echo "$running" | grep -qi "$svc"; then
                check "  $svc" "PASS" "running"
            else
                check "  $svc" "WARN" "not detected"
            fi
        done
    else
        check "Containers running" "FAIL" "none — run docker compose up -d"
    fi
else
    check "Docker" "FAIL" "not found"
fi
echo ""

# ── 3. DISK SPACE ───────────────────────────────────────
echo "3. DISK SPACE"
home_avail=$(df -BG "$HOME" 2>/dev/null | tail -1 | awk '{print $4}' | tr -d 'G')
if [ -n "$home_avail" ] && [ "$home_avail" -gt 10 ]; then
    check "Home partition" "PASS" "${home_avail}G available"
elif [ -n "$home_avail" ]; then
    check "Home partition" "WARN" "only ${home_avail}G free"
else
    check "Home partition" "WARN" "could not determine"
fi
echo ""

# ── 4. SCRIPTS PRESENT ─────────────────────────────────
echo "4. INGESTION SCRIPTS"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
for script in notebook_ocr.py voice_pipe.sh; do
    [ -f "$SCRIPT_DIR/$script" ] && check "$script" "PASS" "present" || check "$script" "FAIL" "MISSING"
done
python3 -c "import httpx" 2>/dev/null && check "Python httpx" "PASS" "installed" || check "Python httpx" "WARN" "will auto-install"
echo ""

# ── 5. NETWORK ──────────────────────────────────────────
echo "5. NETWORK"
ping -c1 -W2 8.8.8.8 &>/dev/null && check "Internet" "PASS" "reachable" || check "Internet" "WARN" "no response"
command -v tailscale &>/dev/null && {
    ts=$(tailscale status --json 2>/dev/null | jq -r '.Self.Online // false' 2>/dev/null)
    [ "$ts" = "true" ] && check "Tailscale" "PASS" "online" || check "Tailscale" "WARN" "not connected"
} || check "Tailscale" "WARN" "not installed"
echo ""

# ── 6. SMOKE TEST ───────────────────────────────────────
echo "6. VISION MODEL SMOKE TEST"
if curl -s "$OLLAMA_HOST/api/tags" > /dev/null 2>&1; then
    echo "  Testing model response (30s timeout)..."
    resp=$(curl -s --max-time 30 "$OLLAMA_HOST/api/generate" \
        -d "{\"model\":\"$VISION_MODEL\",\"prompt\":\"Say OK.\",\"stream\":false}" 2>/dev/null)
    echo "$resp" | jq -e '.response' > /dev/null 2>&1 && \
        check "Model responds" "PASS" "$(echo "$resp" | jq -r '.response' | head -c 40)" || \
        check "Model responds" "FAIL" "no response — try: ollama pull $VISION_MODEL"
else
    check "Model responds" "FAIL" "Ollama not reachable"
fi
echo ""

# ── SUMMARY ─────────────────────────────────────────────
echo "══════════════════════════════════════════════════════"
echo "  PASS: $PASS  |  FAIL: $FAIL  |  WARN: $WARN"
[ "$FAIL" -eq 0 ] && echo "  STATUS: ✅ READY FOR INGESTION" || echo "  STATUS: ❌ $FAIL BLOCKERS — resolve before 1:30"
echo "══════════════════════════════════════════════════════"
rm -f /tmp/ollama_tags.json
exit "$FAIL"
