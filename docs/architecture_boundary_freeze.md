# Architecture Boundary Freeze

## Canonical Ownership

- Archimedes owns canonical truth: task meaning, objectives, done conditions, artifact linkage, operator decisions, and user-facing state.
- Hydra owns runtime execution: workflow lifecycle, policy enforcement, approvals, adapter calls, retries, audit traces, and synchronization mechanics.
- Hydra tables are companion runtime tables that support Archimedes. They are not an independent product database.

## Runtime Ledger Lineage

- Workflow lineage is `workflow_run -> workflow_step -> action_request -> action_attempt`.
- `workflow_run` records the durable execution envelope for a workflow instance.
- `workflow_step` records ordered step progression inside a workflow run.
- `action_request` records a bounded adapter operation authorized by an execution envelope.
- `action_attempt` records each concrete try of that adapter operation, including retryable and fatal outcomes.

## Boundary Rules

- Archimedes remains the canonical system of record for task semantics.
- Hydra may observe, sync, classify, queue, and execute within an approved envelope, but it may not silently rewrite operator-owned fields.
- Audit, approval, policy, idempotency, and external-object mapping tables exist to explain and constrain execution, not to replace Archimedes truth.
- Any future runtime table must be justified as a companion execution concern under Hydra, not as a second canonical store.
