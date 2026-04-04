# Workflow Catalog v0.1

## `asana_sync_in_v1`

- Trigger conditions: manual sync request, webhook follow-up, or scheduled reconciliation run.
- Inputs: `project_gid`.
- Outputs: sync counts `{inserted, updated, total}` from the shadow task ledger.
- Approval gates: none in v0.1. Read/write activity is bounded to the Asana task surface and requires idempotency keys for write-capable activities.
- Rollback behavior: no destructive rollback. Re-running the workflow is the recovery path because shadow task upserts are idempotent.

## `drift_detect_v1`

- Trigger conditions: detected external change event, operator request, or periodic drift scan.
- Inputs: `subject_id`.
- Outputs: drift result payload including `drift_detected` and any review flags to raise.
- Approval gates: none in v0.1. Drift creates review work; it does not rewrite operator-owned fields.
- Rollback behavior: none. Review flags are advisory and require operator or gated follow-on action.

## `gated_execution_v1`

- Trigger conditions: any proposed step that could cross execution boundaries, incur side effects, or require escalation.
- Inputs: payload with `current_intent`, `proposed_step`, and `requested_operation`.
- Outputs: boundary evaluation with classification, decision, and rationale.
- Approval gates: approval gates are expected when the policy path resolves to `escalate` or when a later execution stage requires human authorization.
- Rollback behavior: none. The workflow records or queues the decision; blocked work remains blocked until a new approved run supersedes it.
