from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from app.models import ProcessResponse, CXState


class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Job:
    id: str
    status: JobStatus
    created_at: datetime
    updated_at: datetime
    result: ProcessResponse | None = None
    error: str | None = None


_jobs: dict[str, Job] = {}


def create_job() -> Job:
    now = datetime.now(timezone.utc)
    job = Job(
        id=str(uuid.uuid4()),
        status=JobStatus.PENDING,
        created_at=now,
        updated_at=now,
    )
    _jobs[job.id] = job
    return job


def get_job(job_id: str) -> Job | None:
    return _jobs.get(job_id)


def _update_job(job_id: str, **kwargs: Any) -> None:
    job = _jobs.get(job_id)
    if job is None:
        return
    for key, value in kwargs.items():
        setattr(job, key, value)
    job.updated_at = datetime.now(timezone.utc)


async def run_job(job_id: str, initial_state: CXState) -> None:
    from app.graph import cx_graph

    _update_job(job_id, status=JobStatus.PROCESSING)
    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(None, cx_graph.invoke, initial_state)
        response = ProcessResponse(
            ticket_id=result["normalized_ticket"].get("ticket_id", ""),
            status=result["status"],
            triage=result.get("triage"),
            route=result.get("route", ""),
            final_response=result.get("final_response", ""),
            guardrail_result=result.get("guardrail_result"),
            qa_scores=result.get("qa_scores"),
            trace=result.get("trace", []),
        )
        _update_job(job_id, status=JobStatus.COMPLETED, result=response)
    except Exception as exc:
        _update_job(job_id, status=JobStatus.FAILED, error=str(exc))
