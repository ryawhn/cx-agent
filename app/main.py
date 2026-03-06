from __future__ import annotations

import json
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.models import TicketRequest, ProcessResponse, CXState
from app.graph import cx_graph

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


@app.post("/api/process", response_model=ProcessResponse)
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

    result = cx_graph.invoke(initial_state)

    return ProcessResponse(
        ticket_id=result["normalized_ticket"].get("ticket_id", ""),
        status=result["status"],
        triage=result.get("triage"),
        route=result.get("route", ""),
        final_response=result.get("final_response", ""),
        guardrail_result=result.get("guardrail_result"),
        qa_scores=result.get("qa_scores"),
        trace=result.get("trace", []),
    )


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
