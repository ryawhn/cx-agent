from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
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
    retry_count: int = 0
    max_retries: int = 3


# ---------------------------------------------------------------------------
# In-memory stores
# ---------------------------------------------------------------------------

_jobs: dict[str, Job] = {}
_dlq: dict[str, Job] = {}

# content_hash -> (job_id, created_at)
_dedup_cache: dict[str, tuple[str, datetime]] = {}

_queue: asyncio.Queue[tuple[str, CXState]] = asyncio.Queue()
_worker_tasks: list[asyncio.Task[None]] = []


# ---------------------------------------------------------------------------
# Dedup
# ---------------------------------------------------------------------------

def check_duplicate(content_hash: str, window_seconds: int = 600) -> str | None:
    """Return an existing job_id if the same content was submitted within the window."""
    _prune_dedup_cache(window_seconds)
    entry = _dedup_cache.get(content_hash)
    if entry is None:
        return None
    job_id, created_at = entry
    if (datetime.now(timezone.utc) - created_at).total_seconds() <= window_seconds:
        return job_id
    del _dedup_cache[content_hash]
    return None


def register_dedup(content_hash: str, job_id: str) -> None:
    _dedup_cache[content_hash] = (job_id, datetime.now(timezone.utc))


def _prune_dedup_cache(window_seconds: int) -> None:
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=window_seconds)
    stale = [h for h, (_, ts) in _dedup_cache.items() if ts < cutoff]
    for h in stale:
        del _dedup_cache[h]


# ---------------------------------------------------------------------------
# Job CRUD
# ---------------------------------------------------------------------------

def create_job() -> Job:
    from app.config import settings

    now = datetime.now(timezone.utc)
    job = Job(
        id=str(uuid.uuid4()),
        status=JobStatus.PENDING,
        created_at=now,
        updated_at=now,
        max_retries=settings.max_job_retries,
    )
    _jobs[job.id] = job
    return job


def get_job(job_id: str) -> Job | None:
    return _jobs.get(job_id)


def get_dlq() -> list[Job]:
    return list(_dlq.values())


def _update_job(job_id: str, **kwargs: Any) -> None:
    job = _jobs.get(job_id)
    if job is None:
        return
    for key, value in kwargs.items():
        setattr(job, key, value)
    job.updated_at = datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Queue + worker pool
# ---------------------------------------------------------------------------

async def enqueue_job(job_id: str, state: CXState) -> None:
    await _queue.put((job_id, state))


async def _delayed_enqueue(job_id: str, state: CXState, delay: float) -> None:
    await asyncio.sleep(delay)
    await enqueue_job(job_id, state)


async def _worker() -> None:
    """Pull jobs from the shared queue indefinitely."""
    while True:
        job_id, state = await _queue.get()
        try:
            await _run_job(job_id, state)
        finally:
            _queue.task_done()


def start_workers() -> None:
    """Spawn a bounded pool of workers. Call once on app startup."""
    from app.config import settings

    for _ in range(settings.max_workers):
        task = asyncio.create_task(_worker())
        _worker_tasks.append(task)


# ---------------------------------------------------------------------------
# Job execution with retry + DLQ
# ---------------------------------------------------------------------------

async def _run_job(job_id: str, initial_state: CXState) -> None:
    from app.graph import cx_graph

    job = _jobs.get(job_id)
    if job is None:
        return

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
        job.retry_count += 1
        job.updated_at = datetime.now(timezone.utc)

        if job.retry_count < job.max_retries:
            delay = float(2 ** job.retry_count)
            _update_job(job_id, status=JobStatus.PENDING, error=str(exc))
            asyncio.create_task(
                _delayed_enqueue(job_id, initial_state, delay)
            )
        else:
            _update_job(job_id, status=JobStatus.FAILED, error=str(exc))
            _dlq[job_id] = _jobs[job_id]
