# Ollama Migration Runbook

This runbook covers the codeable part of the "sensitive reasoning sessions" migration:
moving LiteLLM from a locally attached Ollama instance to a GPU-backed Ollama host
reachable over Tailscale.

## 1. Identify the GPU-capable host

Run on each candidate machine:

```bash
lspci | grep -i 'vga\\|3d\\|display'
nvidia-smi
```

If no GPU is present or `nvidia-smi` is unavailable, keep that host out of the
Ollama migration path.

<!-- TODO(asana:1213918469348670): Human decision required. Pick the GPU-capable host and record its Tailscale IP before cutover. -->

## 2. Install and warm Ollama on the chosen host

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull llama3:8b
```

Verify the host is serving on port `11434`:

```bash
curl -sf http://127.0.0.1:11434/api/tags
```

## 3. Point LiteLLM at the remote host

Set the target base URL in your local `.env` or shell:

```bash
export OLLAMA_API_BASE=http://<tailscale-ip>:11434
```

Then restart LiteLLM with the remote override:

```bash
docker compose \
  -f infra/compose/docker-compose.dev.yml \
  -f infra/compose/docker-compose.ollama-remote.yml \
  up -d litellm
```

The override swaps LiteLLM onto
[`infra/compose/litellm-config.remote-ollama.yaml`](/home/radar41/Archimedes/infra/compose/litellm-config.remote-ollama.yaml),
which resolves `OLLAMA_API_BASE` at runtime.

## 4. Validate the route

```bash
OLLAMA_API_BASE=http://<tailscale-ip>:11434 ./infra/scripts/validate-stack.sh
```

Focus on:

- remote Ollama health
- remote model presence
- LiteLLM readiness
- LiteLLM to Ollama completion

## 5. Roll back if needed

To return LiteLLM to the local/container-attached Ollama path:

```bash
docker compose -f infra/compose/docker-compose.dev.yml up -d litellm
```
