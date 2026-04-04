from __future__ import annotations

import uuid

from sqlalchemy import select
from temporalio import activity

from backend.app.adapters.asana.service import get_task
from backend.app.db import SessionLocal
from backend.app.models.shadow import ShadowTask
from backend.app.services.audit import write_audit_event
from backend.app.services.propagation import ReviewFlagRecord, persist_review_flags


def _task_section(memberships: list[dict]) -> str | None:
    if not memberships:
        return None
    section = memberships[0].get("section") if isinstance(memberships[0], dict) else None
    if isinstance(section, dict):
        return section.get("name")
    return None


def _task_status(completed: bool | None) -> str:
    return "completed" if completed else "incomplete"


@activity.defn
async def collect_drift_inputs(payload: dict) -> dict:
    changed_gids = {
        event["after"]["asana_gid"]
        for event in payload.get("change_events", [])
        if event.get("after") and event["after"].get("asana_gid")
    }
    with SessionLocal() as session:
        stmt = select(ShadowTask)
        if changed_gids:
            stmt = stmt.where(ShadowTask.asana_gid.in_(changed_gids))
        shadow_tasks = session.execute(stmt).scalars().all()

    live_state: dict[str, dict] = {}
    for task in shadow_tasks:
        live_task = await get_task(task.asana_gid)
        live_state[task.asana_gid] = {
            "title": live_task.name,
            "status": _task_status(live_task.completed),
            "section": _task_section(live_task.memberships),
        }

    return {
        "project_gid": payload.get("project_gid"),
        "shadow_state": {
            task.asana_gid: {
                "id": str(task.id),
                "asana_gid": task.asana_gid,
                "title": task.title,
                "status": task.status,
                "section": task.section,
            }
            for task in shadow_tasks
        },
        "live_state": live_state,
    }


@activity.defn
async def compare_canonical_and_external_state(inputs: dict) -> dict:
    drifts: list[dict] = []
    for asana_gid, shadow_state in inputs["shadow_state"].items():
        live_state = inputs["live_state"].get(asana_gid, {})
        changed_fields = sorted(
            field
            for field in ("title", "status", "section")
            if shadow_state.get(field) != live_state.get(field)
        )
        if changed_fields:
            drifts.append(
                {
                    "task_id": shadow_state["id"],
                    "asana_gid": asana_gid,
                    "changed_fields": changed_fields,
                    "shadow_state": shadow_state,
                    "live_state": live_state,
                }
            )
    return {"drift_detected": bool(drifts), "drifts": drifts}


@activity.defn
async def record_drift_findings(result: dict) -> dict:
    created_flags = 0
    audit_events = 0
    with SessionLocal() as session:
        for drift in result["drifts"]:
            if {"title", "section"} & set(drift["changed_fields"]):
                persist_review_flags(
                    session,
                    [
                        ReviewFlagRecord(
                            task_id=uuid.UUID(drift["task_id"]),
                            flag_type="operator_review",
                            summary=f"Operator-owned drift detected for Asana task {drift['asana_gid']}.",
                            detail_json=drift,
                        )
                    ],
                )
                created_flags += 1

            write_audit_event(
                session,
                event_type="drift_detected",
                subject_type="shadow_task",
                subject_id=uuid.UUID(drift["task_id"]),
                summary=f"Field-level drift detected for Asana task {drift['asana_gid']}.",
                detail_json=drift,
            )
            audit_events += 1

    return {"created_flags": created_flags, "audit_events": audit_events}
