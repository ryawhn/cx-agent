from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.models import TicketRequest, JobResponse, CXState
from app.jobs import (
    check_duplicate,
    create_job,
    enqueue_job,
    get_dlq,
    get_job,
    register_dedup,
    start_workers,
    JobStatus,
)

STATIC_DIR = Path(__file__).resolve().parent / "static"
TICKETS_PATH = Path(__file__).resolve().parent.parent / "data" / "tickets.json"

app = FastAPI(title="CX Agent", description="AI CX Ticket Triage + Auto-Draft Agent")


@app.on_event("startup")
async def startup_event() -> None:
    start_workers()


@app.get("/")
async def serve_frontend():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.get("/api/tickets/samples")
async def sample_tickets():
    with open(TICKETS_PATH) as f:
        tickets = json.load(f)
    return tickets


@app.post("/api/process")
async def process_ticket(req: TicketRequest):
    # Body size guard — reject oversized tickets before any queue work
    body_text = req.body or ""
    if len(body_text.encode()) > settings.max_body_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"Ticket body exceeds the {settings.max_body_bytes}-byte limit.",
        )

    # Dedup — return existing job_id if same content was submitted recently
    email = req.customer_email or ""
    subject = req.subject or ""
    content_hash = hashlib.sha256(
        f"{email}|{subject}|{body_text}".encode()
    ).hexdigest()

    existing_job_id = check_duplicate(content_hash, settings.dedup_window_seconds)
    if existing_job_id is not None:
        return JSONResponse(
            status_code=200,
            content={"job_id": existing_job_id, "deduplicated": True},
        )

    initial_state: CXState = {
        "ticket": req.model_dump(),
        "normalized_ticket": {},
        "triage": None,
        "route": "",
        "context_docs": [],
        "draft_response": "",
        "guardrail_result": None,
        "qa_scores": None,
        "attempt": 0,
        "final_response": "",
        "status": "processing",
        "trace": [],
    }

    job = create_job()
    register_dedup(content_hash, job.id)
    await enqueue_job(job.id, initial_state)

    return JSONResponse(
        status_code=202,
        content={"job_id": job.id, "deduplicated": False},
    )


# Must be registered before /api/jobs/{job_id} so FastAPI doesn't treat
# the literal "dlq" as a job_id path parameter.
@app.get("/api/jobs/dlq")
async def dead_letter_queue():
    return [
        {
            "job_id": j.id,
            "status": j.status.value,
            "retry_count": j.retry_count,
            "error": j.error,
            "created_at": j.created_at.isoformat(),
            "updated_at": j.updated_at.isoformat(),
        }
        for j in get_dlq()
    ]


@app.get("/api/jobs/{job_id}", response_model=JobResponse)
async def get_job_status(job_id: str):
    job = get_job(job_id)
    if job is None:
        return JSONResponse(status_code=404, content={"detail": "Job not found"})
    return JobResponse(
        job_id=job.id,
        status=job.status.value,
        created_at=job.created_at.isoformat(),
        updated_at=job.updated_at.isoformat(),
        result=job.result,
        error=job.error,
    )


@app.websocket("/ws/jobs/{job_id}")
async def job_websocket(websocket: WebSocket, job_id: str):
    await websocket.accept()
    try:
        while True:
            job = get_job(job_id)
            if job is None:
                await websocket.send_json({"error": "Job not found"})
                break

            payload = JobResponse(
                job_id=job.id,
                status=job.status.value,
                created_at=job.created_at.isoformat(),
                updated_at=job.updated_at.isoformat(),
                result=job.result,
                error=job.error,
            ).model_dump()

            await websocket.send_json(payload)

            if job.status in (JobStatus.COMPLETED, JobStatus.FAILED):
                break

            await asyncio.sleep(0.5)
    except WebSocketDisconnect:
        pass


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
