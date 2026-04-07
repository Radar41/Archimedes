#!/usr/bin/env bash
# Decrypt SOPS-encrypted secrets into the compose .env file.
# Usage: ./infra/scripts/decrypt-env.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
ENCRYPTED="${REPO_ROOT}/infra/secrets/compose.enc.env"
PLAINTEXT="${REPO_ROOT}/infra/compose/.env"

if [ ! -f "$ENCRYPTED" ]; then
  echo "ERROR: encrypted file not found: $ENCRYPTED" >&2
  exit 1
fi

sops decrypt --output-type dotenv "$ENCRYPTED" > "$PLAINTEXT"
echo "Decrypted → $PLAINTEXT ($(wc -l < "$PLAINTEXT") vars)"
