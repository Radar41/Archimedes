# Startup Runbook

## 1. Start local infrastructure

```bash
docker compose -f infra/compose/docker-compose.dev.yml up -d
```

If LiteLLM should target a remote Ollama host over Tailscale instead of the
default local endpoint, apply the remote override described in
[`docs/runbook_ollama_migration.md`](/home/radar41/Archimedes/docs/runbook_ollama_migration.md).

## 2. Apply database migrations

```bash
make migrate
```

## 3. Boot the FastAPI control plane

```bash
make dev
```

## 4. Launch the Streamlit operator console

```bash
streamlit run ops_console/streamlit_app/health.py
```

Additional pages:

```bash
streamlit run ops_console/streamlit_app/runs.py
streamlit run ops_console/streamlit_app/drift_queue.py
```

## 5. Start the Temporal worker

Register the workflow and activity modules in the worker process, then start it against the configured Temporal namespace.

```bash
python3 -m backend.app.workers.temporal_worker
```

## 6. Verify system health

- `GET /health` for API and database reachability.
- Streamlit Health page for adapter reachability and last sync time.
- Inspect `workflow_run`, `approval_gate`, and `review_flag` tables after first workflow execution.
- Run `./infra/scripts/validate-stack.sh` to validate the local or remote Ollama route, LiteLLM, Langfuse, Temporal, MinIO, Tailscale, and SOPS wiring.
