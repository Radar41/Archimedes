from __future__ import annotations

import asyncio
import os

from temporalio.client import Client
from temporalio.worker import Worker

from backend.app.workflows.activities.asana_activities import (
    post_evidence_comment_activity,
    sync_tasks_activity,
    update_task_status_activity,
)
from backend.app.workflows.activities.asana_sync import (
    consume_inbox_events,
    fetch_asana_project_snapshot,
    upsert_shadow_tasks,
)
from backend.app.workflows.activities.drift import (
    collect_drift_inputs,
    compare_canonical_and_external_state,
    record_drift_findings,
)
from backend.app.workflows.activities.filesystem import scan_filesystem_activity
from backend.app.workflows.activities.gated_execution import (
    enqueue_or_record_decision,
    evaluate_execution_boundary,
)
from backend.app.workflows.activities.github_activities import (
    collect_evidence_activity,
    create_branch_activity,
    create_pr_activity,
)
from backend.app.workflows.asana_sync_in_v1 import AsanaSyncInV1Workflow as AsanaSyncWorkflow
from backend.app.workflows.drift_detect_v1 import DriftDetectV1Workflow as DriftDetectWorkflow
from backend.app.workflows.gated_execution_v1 import GatedExecutionV1Workflow as GatedExecutionWorkflow

TASK_QUEUE = "archimedes-main"


async def main() -> None:
    client = await Client.connect(os.getenv("TEMPORAL_ADDRESS", "localhost:7233"))
    worker = Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[
            AsanaSyncWorkflow,
            DriftDetectWorkflow,
            GatedExecutionWorkflow,
        ],
        activities=[
            fetch_asana_project_snapshot,
            upsert_shadow_tasks,
            consume_inbox_events,
            sync_tasks_activity,
            post_evidence_comment_activity,
            update_task_status_activity,
            collect_drift_inputs,
            compare_canonical_and_external_state,
            record_drift_findings,
            scan_filesystem_activity,
            evaluate_execution_boundary,
            enqueue_or_record_decision,
            create_branch_activity,
            create_pr_activity,
            collect_evidence_activity,
        ],
    )
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
