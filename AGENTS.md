# ARCHIMEDES / HYDRA — Codex Agent Instructions

## Project Identity

This is the **Archimedes/Hydra** system. Archimedes is the canonical system of record and user-facing control surface. Hydra is the bounded execution, orchestration, governance, and integration runtime beneath Archimedes. You are working inside the Archimedes repository.

## Architecture (frozen — do not change without explicit human approval)

- **Archimedes** = canonical task graph, conversations, documents, artifacts, routing policy, user-facing surfaces
- **Hydra** = workflow execution lifecycle, policy enforcement, adapter calls, evidence collection, sync/reconciliation with external systems
- **Asana** = daily working ledger and external memory surface (stays — not being replaced)
- **GitHub** = implementation and evidence surface

Hydra is NOT the top-level product. It is the execution plane BENEATH Archimedes. Do not promote Hydra above Archimedes in any design decision.

## Frozen Technology Stack

| Service | Role |
|---------|------|
| FastAPI | Control plane / API / BFF |
| PostgreSQL + pgvector | Canonical relational store + vector retrieval |
| MinIO | Object and artifact storage (S3-compatible) |
| Temporal | Durable workflow orchestration |
| Langfuse + OpenTelemetry | Tracing, evals, observability |
| LiteLLM | Model gateway/router (all inference goes through this) |
| Ollama | Local inference engine (native install, not Docker) |
| MCP | Connector/tool contract boundary |
| Tailscale | Private mesh VPN for worker traffic |
| SOPS + age | Secrets encryption |
| Alembic | Schema migration discipline |
| Streamlit | First operator UI surface |

Do NOT add frameworks, services, or infrastructure not on this list without explicit human approval.

## Asana Integration

- Workspace GID: `952160553655161`
- Project GID: `1213914133387697`
- Project name: ARCHIMEDES — Hydra Runtime
- 25 tasks across 5 sections (Charter & Contracts, Runtime Core, Asana Bridge, Policy/Approval/Evidence, Operator Console & Cutover)
- Auth: Personal Access Token (PAT) as bearer token
- API base: `https://app.asana.com/api/1.0/`
- Rate limits: 1500 req/min (paid tier). Always respect 429 + Retry-After.
- Phase 1 is READ-ONLY. Do not write to Asana without explicit approval.

## Repository Layout

```
backend/
  app/
    adapters/asana/    — httpx-based Asana REST client
    adapters/github/   — GitHub adapter for PRs/evidence
    api/               — FastAPI route modules
    models/            — SQLAlchemy ORM models
    services/          — Business logic (scope_gate.py, audit.py, etc.)
    workflows/         — Temporal workflow definitions
    contracts/         — Shared Pydantic request/response schemas
  migrations/versions/ — Alembic migration files
  tests/               — pytest test suite
ops_console/streamlit_app/ — Streamlit operator console
infra/compose/         — Docker Compose files
infra/secrets/         — SOPS-encrypted secrets only
docs/                  — Runbooks and documentation
```

## Hard Rules (Architecture Lock v1.2)

1. No plaintext secrets. Everything through SOPS + age.
2. All model inference traffic through LiteLLM. Never call OpenAI/Anthropic/Ollama directly from application code.
3. All long-running or multi-step work through Temporal workflows.
4. All worker traffic stays on the Tailscale mesh.
5. SSH execution is allowlist-only and fully audited.
6. No self-approval. An executing agent cannot approve its own output.
7. Operator-owned meaning fields (task objectives, done conditions) are NEVER silently rewritten.
8. Every "done" claim must point to an artifact.
9. No stack changes without revising the architecture lock document.
10. Human (Adrian) remains final authority for architecture, schema, approval gates, and overrides.

## Code Standards

- Python 3.12+, full type hints
- Pydantic v2 for all data models and API schemas
- SQLAlchemy 2.0+ ORM for database models
- Alembic for all schema migrations (no manual DDL ever)
- httpx for async HTTP (not requests)
- pytest for testing
- Every function either works or raises NotImplementedError with a comment

## Testing

```bash
make test       # run full test suite
make lint       # run linters
make dev        # boot FastAPI dev server
make migrate    # run alembic upgrade head
```

## Current Phase: Phase 1 Bootstrap

BUILD:
- Repo skeleton, pyproject.toml, Makefile, .devcontainer
- docker-compose.dev.yml with Postgres
- Alembic init + first migration: shadow_tasks, inbox_events, id_mappings
- Asana adapter: read-only (list_project_tasks, get_task, list_stories, list_sections)
- Sync engine: POST /sync/inbound pulls all tasks, upserts to shadow_tasks
- GET /health, GET /version, GET /tasks endpoints
- Tests that pass

DO NOT BUILD (deferred to Phase 2+):
- Temporal workflows
- Webhook receiver
- MinIO / artifact storage
- Streamlit console
- Write-back to Asana
- Any frontend (Next.js, Tauri)
- Multi-agent orchestration

## Coordination Note

Claude Code (Anthropic) may also be working in this repository. Both agents follow the same architecture lock and hard rules. If you see a CLAUDE.md file, it contains equivalent instructions for the other agent. Do not modify CLAUDE.md. Do not conflict with its contents.
