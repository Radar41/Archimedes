# ARCHIMEDES / HYDRA — Claude Code Instructions

## Project Identity

This is the **Archimedes/Hydra** system. Archimedes is the canonical system of record. Hydra is the bounded execution/orchestration/governance runtime beneath Archimedes. You are working inside the Archimedes repository.

## Architecture (frozen — do not change without explicit approval)

- **Archimedes** = canonical task graph, conversations, documents, artifacts, routing policy, user-facing surfaces
- **Hydra** = workflow execution, policy enforcement, adapter calls, evidence collection, sync/reconciliation
- **Asana** = daily working ledger (stays — not being replaced this phase)
- **GitHub** = implementation and evidence surface

## Frozen Stack

FastAPI | PostgreSQL + pgvector | MinIO | Temporal | Langfuse + OpenTelemetry | LiteLLM | MCP | Tailscale | SOPS + age | Alembic | Streamlit (first UI)

Do NOT introduce new infrastructure, frameworks, or services without explicit human approval.

## Asana Integration

- Workspace GID: `952160553655161`
- Project GID: `1213914133387697`
- Project name: ARCHIMEDES — Hydra Runtime
- Auth: PAT (bearer token via `ASANA_PAT` env var)
- API base: `https://app.asana.com/api/1.0/`
- Rate limits: respect 429 + Retry-After headers
- Phase 1 is READ-ONLY. Do not write back to Asana without explicit approval.

## Repository Structure (from Architecture Lock v1.2)

```
backend/
  app/
    adapters/asana/    — Asana REST adapter
    adapters/github/   — GitHub adapter
    api/               — FastAPI route modules
    models/            — SQLAlchemy ORM models
    services/          — Business logic (scope_gate, audit, etc.)
    workflows/         — Temporal workflow definitions
    contracts/         — Shared request/response schemas
  migrations/versions/ — Alembic migrations
  tests/               — All tests
ops_console/
  streamlit_app/       — Operator console pages
infra/
  compose/             — Docker Compose files
  secrets/             — SOPS-encrypted secrets (never plaintext)
  backup/              — Backup scripts
docs/                  — Runbooks, field dictionaries, setup
```

## Hard Rules

1. No plaintext secrets anywhere. All secrets through SOPS + age.
2. All model traffic through LiteLLM gateway. Never call providers directly.
3. All long-running work through Temporal workflows.
4. All worker traffic on Tailscale mesh.
5. SSH execution is allowlist-only and fully audited.
6. No self-approval. Executing agent cannot approve its own output.
7. No execution without an approved work item.
8. Operator-owned meaning fields are NEVER silently rewritten by automation.
9. Every "done" claim must point to artifacts.
10. Review gates are mandatory where policy requires them.

## Code Standards

- Python 3.12+
- Type hints on all function signatures
- Pydantic models for all API schemas
- SQLAlchemy ORM for all database models
- Alembic for all schema changes (no manual DDL)
- httpx for async HTTP calls
- pytest for all tests
- If a function exists, it works or raises NotImplementedError with a tracking comment

## Current Phase: Phase 1 Bootstrap

Focus ONLY on:
- Repo skeleton + devcontainer + Makefile
- Alembic baseline + shadow tables (shadow_tasks, inbox_events, id_mappings)
- Read-only Asana adapter (httpx, PAT auth, rate-limit handling)
- Inbound sync engine (pull tasks, upsert to shadow_tasks, idempotent)
- Health + version + tasks API endpoints
- Tests that pass

Do NOT build in Phase 1:
- Temporal workflows (Phase 2)
- Webhook receiver (Phase 2)
- MinIO / artifact storage (Phase 2)
- Streamlit console (Phase 2)
- Write-back to Asana (Phase 2)
- Next.js / frontend (Phase 3+)
- Multi-agent orchestration (Phase 3+)

## Session Discipline

- Update this CLAUDE.md at the end of every session with key decisions and patterns
- Commit frequently with meaningful messages
- Run `make test` before declaring anything complete
- If you discover a prerequisite that's missing, say so — don't silently work around it
