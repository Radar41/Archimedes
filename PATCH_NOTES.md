# WART MVP — Patch Notes (April 7, 2026)

Applied over `archimedes-real-mvp.tar.gz` from OpenAI session. 25/25 tests pass.

## Patch 1: Schema — governance columns + hydra→wart compat

**Files:** `backend/app/core/db.py`, `backend/app/models/schemas.py`, `backend/app/services/repository.py`

Added six governance columns to the `tasks` table:
- `x_mode` (default `x1_align`) — assistance scale band
- `model_tier` (default `sonnet`) — Haiku/Sonnet/Opus routing
- `owner_mode` (default `human`) — human vs agent ownership
- `work_class` (default `build`) — build/fix/research/review/ops
- `authority_level` (default `medium`) — low/medium/high
- `review_required` (default `1`) — boolean gate

Renamed `hydra_mode` → `wart_mode` with backward compatibility:
- New schema uses `wart_mode` as the canonical column
- `TaskCreate` and `TaskPatch` accept legacy `hydra_mode` field
- Repository maps `hydra_mode` → `wart_mode` on create and patch
- `Database.initialize()` includes a migration that copies `hydra_mode` data to `wart_mode` if upgrading a legacy DB
- **Rationale:** The WART audit documents conflicting source layers — the rename is logged but not executed. This patch makes `wart_mode` canonical while preserving read/write compat during the transition window.

Added `adjacent_queue` table for Expansion Ledger storage.

## Patch 2: Project API

**Files:** `backend/app/api/tasks.py`, `backend/app/services/repository.py`

Added:
- `GET /projects/{project_id}` — project detail
- `GET /projects/{project_id}/tasks` — list tasks for a project, with optional `?status=` filter
- `Repository.get_project()` method

## Patch 3: EBL — task-aware scope evaluation + adjacent queue

**Files:** `backend/app/services/scope_gate.py`, `backend/app/api/scope.py`

`evaluate_scope()` now accepts an optional `task` dict (from DB). When provided, the evaluation uses the task's actual `x_mode`, `work_class`, and `authority_level` instead of falling back to request-level defaults.

New enforcement gates (in evaluation order):
1. **NEW_PROJECT_MARKERS** → C_NEW_PROJECT_ISOLATE (unchanged)
2. **ADJACENT_MARKERS** → B_ADJACENT_DEFER (unchanged)
3. **X-band enforcement** → blocks side-effecting ops (`ssh_execute`, `model_call`, `adapter_write`, etc.) when `x_mode` is `x0_human` or `x1_align`
4. **Work_class mismatch** → blocks operations not permitted for the task's `work_class` (e.g., `create_project` blocked for `review` tasks)
5. **Intent alignment** → term-overlap heuristic (unchanged)

Scope API (`POST /scope/evaluate`) now:
- Looks up the task from DB when `current_task_id` is provided
- Auto-writes to `adjacent_queue` table when classification is B or C

Adjacent queue endpoints:
- `GET /tasks/{id}/adjacent-queue` — list queued items
- `POST /tasks/{id}/adjacent-queue/{item_id}/promote`
- `POST /tasks/{id}/adjacent-queue/{item_id}/dismiss`

## Patch 4: Dependency-driven downstream propagation

**Files:** `backend/app/services/repository.py`, `backend/app/api/tasks.py`

`create_change_event()` now queries `task_dependencies` and opens `upstream_changed` review flags on all downstream dependents when the source change triggers flagging (D2/D3 deviation or deviation_detected/scope_blocked event).

Severity mapping by `dep_type`:
- `hard_precedes`, `blocks` → high
- `revises` → medium
- other → low
- D3 deviation on upstream → escalates all downstream flags to high regardless of dep_type

New endpoints:
- `POST /tasks/{id}/dependencies?depends_on_task_id=...&dep_type=hard_precedes`
- `GET /tasks/{id}/dependencies`

Repository methods: `add_dependency()`, `list_dependencies()`, `_propagate_downstream_flags()`, `_open_flag()`.

## Patch 5: Tests

**File:** `backend/tests/test_api.py`

25 tests covering:
- Health check (1)
- Governance field defaults, explicit values, patching (3)
- Hydra→WART backward compat on create and patch (2)
- Project list, detail, 404, project tasks, status filter (5)
- EBL: aligned allow, architecture jump block, x-band block, x2 allow, work_class mismatch (5)
- Adjacent queue: auto-write on block, promote, dismiss (2)
- Downstream propagation: source flag, hard_precedes, revises, D3 escalation, multi-downstream (5)
- Approval + workflow (1)
- Audit trail completeness (1)
