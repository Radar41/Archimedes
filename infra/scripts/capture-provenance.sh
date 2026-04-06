#!/usr/bin/env bash
# Capture a lightweight provenance snapshot for the current Archimedes workspace.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
OUT_DIR="${1:-${REPO_ROOT}/docs/provenance}"
STAMP="$(date -u +"%Y%m%dT%H%M%SZ")"
OUT_FILE="${OUT_DIR}/provenance-${STAMP}.md"

mkdir -p "$OUT_DIR"

{
  echo "# Provenance Snapshot"
  echo ""
  echo "- Generated (UTC): $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  echo "- Hostname: $(hostname)"
  echo "- Repository: ${REPO_ROOT}"
  echo ""

  echo "## Git"
  echo ""
  echo "- Branch: $(git -C "$REPO_ROOT" rev-parse --abbrev-ref HEAD)"
  echo "- HEAD: $(git -C "$REPO_ROOT" rev-parse HEAD)"
  echo ""
  echo "### Working Tree"
  echo ""
  echo '```text'
  git -C "$REPO_ROOT" status --short
  echo '```'
  echo ""
  echo "### Recent Commits"
  echo ""
  echo '```text'
  git -C "$REPO_ROOT" log --oneline -5
  echo '```'
  echo ""

  echo "## Runtime Surface"
  echo ""
  if command -v docker >/dev/null 2>&1; then
    echo "### Compose Services"
    echo ""
    echo '```text'
    docker compose -f "$REPO_ROOT/infra/compose/docker-compose.dev.yml" ps || true
    echo '```'
    echo ""
  else
    echo "- Docker unavailable on this host."
    echo ""
  fi

  echo "## Network"
  echo ""
  if command -v tailscale >/dev/null 2>&1; then
    echo "- Tailscale IPv4: $(tailscale ip -4 2>/dev/null | head -n 1 || echo unavailable)"
  else
    echo "- Tailscale unavailable on this host."
  fi
  echo ""

  echo "## Canonical Docs Checksums"
  echo ""
  echo '```text'
  sha256sum \
    "$REPO_ROOT/docs/architecture_boundary_freeze.md" \
    "$REPO_ROOT/docs/workflow_catalog_v0.1.md"
  echo '```'
} > "$OUT_FILE"

echo "$OUT_FILE"
