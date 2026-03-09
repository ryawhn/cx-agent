from __future__ import annotations

import asyncio
import json
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.models import TicketRequest, JobResponse, CXState
from app.jobs import create_job, get_job, run_job, JobStatus

STATIC_DIR = Path(__file__).resolve().parent / "static"
TICKETS_PATH = Path(__file__).resolve().parent.parent / "data" / "tickets.json"

app = FastAPI(title="CX Agent", description="AI CX Ticket Triage + Auto-Draft Agent")


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


@app.post("/api/process", status_code=202)
async def process_ticket(req: TicketRequest):
    ticket_dict = req.model_dump()

    initial_state: CXState = {
        "ticket": ticket_dict,
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
    asyncio.create_task(run_job(job.id, initial_state))
    return {"job_id": job.id}


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
