#!/usr/bin/env bash
# E2E validation for the Archimedes infrastructure stack.
# Probes each service endpoint and reports pass/fail.
set -uo pipefail

OLLAMA_API_BASE="${OLLAMA_API_BASE:-http://localhost:11434}"
OLLAMA_EXPECTED_MODEL="${OLLAMA_EXPECTED_MODEL:-llama3:8b}"
LITELLM_BASE_URL="${LITELLM_BASE_URL:-http://localhost:4000}"

PASS=0
FAIL=0
WARN=0

check() {
  local name="$1" cmd="$2"
  if eval "$cmd" >/dev/null 2>&1; then
    echo "  [PASS] $name"
    ((PASS++))
  else
    echo "  [FAIL] $name"
    ((FAIL++))
  fi
}

warn() {
  local name="$1" msg="$2"
  echo "  [WARN] $name — $msg"
  ((WARN++))
}

echo "=== Archimedes Stack Validation ==="
echo ""

# --- PostgreSQL ---
echo "PostgreSQL (5432):"
check "port open" "nc -z localhost 5432"
check "archimedes_dev database" "docker exec archimedes-postgres psql -U archimedes -d archimedes_dev -c 'SELECT 1'"
check "langfuse_dev database" "docker exec archimedes-postgres psql -U archimedes -d langfuse_dev -c 'SELECT 1'"
echo ""

# --- Temporal ---
echo "Temporal (7233):"
check "gRPC port open" "nc -z localhost 7233"
check "Temporal UI (8233)" "curl -sf http://localhost:8233 -o /dev/null"
echo ""

# --- MinIO ---
echo "MinIO (9000/9001):"
check "health endpoint" "curl -sf http://localhost:9000/minio/health/live"
check "console UI (9001)" "curl -sf http://localhost:9001 -o /dev/null"
# Check buckets via mc inside the container
for bucket in artifacts evidence backups; do
  check "bucket: $bucket" "docker exec compose-minio-1 mc ls local/$bucket/ 2>/dev/null"
done
echo ""

# --- Langfuse ---
echo "Langfuse (3000):"
check "health endpoint" "curl -sf http://localhost:3000/api/public/health"
echo ""

# --- LiteLLM ---
echo "LiteLLM (4000):"
check "readiness" "curl -sf ${LITELLM_BASE_URL}/health/readiness"
LITELLM_KEY="${LITELLM_MASTER_KEY:-sk-litellm-dev-key}"
check "auth with master key" "curl -sf -H 'Authorization: Bearer $LITELLM_KEY' ${LITELLM_BASE_URL}/v1/models -o /dev/null"
# Test each model route (expect auth errors for placeholder keys, but routing must work)
for model in "gpt-4o" "claude-sonnet-4-6"; do
  resp=$(curl -s -H "Authorization: Bearer $LITELLM_KEY" -H "Content-Type: application/json" \
    -d "{\"model\":\"$model\",\"messages\":[{\"role\":\"user\",\"content\":\"hi\"}],\"max_tokens\":1}" \
    ${LITELLM_BASE_URL}/v1/chat/completions 2>&1)
  if echo "$resp" | grep -q "AuthenticationError\|authentication_error\|Incorrect API key"; then
    echo "  [PASS] route $model (upstream auth error = routing works, key is placeholder)"
    ((PASS++))
  elif echo "$resp" | grep -q '"choices"'; then
    echo "  [PASS] route $model (got completion)"
    ((PASS++))
  else
    echo "  [FAIL] route $model — unexpected: $(echo "$resp" | head -c 120)"
    ((FAIL++))
  fi
done
echo ""

# --- Ollama ---
echo "Ollama (${OLLAMA_API_BASE}):"
check "tags endpoint" "curl -sf ${OLLAMA_API_BASE}/api/tags -o /dev/null"
if docker ps --filter name=compose-ollama-1 --format '{{.Status}}' | grep -q Up; then
  check "local container model ${OLLAMA_EXPECTED_MODEL}" "docker exec compose-ollama-1 ollama list 2>/dev/null | grep -q ${OLLAMA_EXPECTED_MODEL}"
else
  check "remote model ${OLLAMA_EXPECTED_MODEL}" "curl -sf ${OLLAMA_API_BASE}/api/tags | grep -q '\"name\":\"${OLLAMA_EXPECTED_MODEL}\"'"
fi
# Test full LiteLLM→Ollama chain
ollama_resp=$(curl -s --max-time 90 -H "Authorization: Bearer $LITELLM_KEY" -H "Content-Type: application/json" \
  -d '{"model":"ollama/llama3:8b","messages":[{"role":"user","content":"Say ok"}],"max_tokens":5}' \
  ${LITELLM_BASE_URL}/v1/chat/completions 2>&1)
if echo "$ollama_resp" | grep -q '"choices"'; then
  echo "  [PASS] LiteLLM → Ollama completion"
  ((PASS++))
else
  echo "  [FAIL] LiteLLM → Ollama — $(echo "$ollama_resp" | head -c 120)"
  ((FAIL++))
fi
echo ""

# --- Tailscale ---
echo "Tailscale:"
if command -v tailscale >/dev/null 2>&1; then
  check "daemon running" "tailscale status >/dev/null 2>&1"
  ts_ip=$(tailscale ip -4 2>/dev/null || echo "none")
  echo "  [INFO] Tailscale IPv4: $ts_ip"
  peer_count=$(tailscale status 2>/dev/null | grep -c "  " || echo 0)
  echo "  [INFO] Peers on tailnet: $peer_count"
else
  echo "  [FAIL] tailscale not installed"
  ((FAIL++))
fi
echo ""

# --- SOPS ---
echo "SOPS + age:"
check "sops installed" "command -v sops"
check "age installed" "command -v age"
check "age key exists" "test -f ~/.config/sops/age/keys.txt"
check "encrypted secrets file" "test -f infra/secrets/compose.enc.env"
check "decrypt roundtrip" "sops decrypt --output-type dotenv infra/secrets/compose.enc.env >/dev/null"
echo ""

# --- Summary ---
echo "=============================="
echo "PASS: $PASS  |  FAIL: $FAIL  |  WARN: $WARN"
if [ "$FAIL" -eq 0 ]; then
  echo "Stack status: ALL CHECKS PASSED"
else
  echo "Stack status: $FAIL FAILURE(S) — review above"
fi
echo "=============================="
exit "$FAIL"
