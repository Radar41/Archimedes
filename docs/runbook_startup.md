# Startup Runbook

## 1. Start local infrastructure

```bash
docker compose -f infra/compose/docker-compose.dev.yml up -d
```

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
python3 -m backend.app.workflows.worker
```

If the worker module is not yet implemented, wire a bootstrap that registers:

- `backend.app.workflows.asana_sync_in_v1.AsanaSyncInV1Workflow`
- `backend.app.workflows.drift_detect_v1.DriftDetectV1Workflow`
- `backend.app.workflows.gated_execution_v1.GatedExecutionV1Workflow`
- `backend.app.workflows.activities.asana_activities`
- `backend.app.workflows.activities.github_activities`

## 6. Verify system health

- `GET /health` for API and database reachability.
- Streamlit Health page for adapter reachability and last sync time.
- Inspect `workflow_run`, `approval_gate`, and `review_flag` tables after first workflow execution.
