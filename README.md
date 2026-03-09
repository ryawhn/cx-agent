# CX Agent — AI Ticket Triage + Auto-Draft

A LangGraph multi-agent pipeline that automates CX ticket triage, response drafting, compliance checking, and quality evaluation for a fintech company.

![Demo](demo.webp)

## Architecture

```
Ticket → Intake → Triage → Router → Drafter → Guardrails → QA/Eval → Response
```

- **Intake** — validates and normalizes incoming tickets
- **Triage** — classifies urgency (P1/P2/P3), category, and sentiment
- **Router** — decides: auto-respond, draft-for-review, or escalate
- **Drafter** — generates responses using RAG over a knowledge base
- **Guardrails** — checks for compliance violations (fintech-specific)
- **QA/Eval** — scores drafts on relevance, tone, and compliance

## Production Scalibility 
- **Multi-model design**: currently use gpt-oss-safeguard for guardrail, fallback to other model such as Gemini when default model not available
- **Async job queue**: `POST /api/process` enqueues a background job and returns a `job_id` in milliseconds; `graph.invoke()` runs in a thread pool via `asyncio.run_in_executor` so the event loop is never blocked. Clients poll `GET /api/jobs/:id` or subscribe via `WS /ws/jobs/:id` for live updates. Currently backed by an in-memory store — swap in Redis or a message broker (GCP Pub/Sub, SQS) for multi-instance deployments.

## Edge Cases

- **Duplicate tickets** — on every `POST /api/process`, the body is fingerprinted with `sha256(email|subject|body)`. If the same hash is seen within 10 minutes, the existing `job_id` is returned immediately (HTTP 200) instead of spawning a duplicate job. Prevents retry storms from frustrated users hammering the submit button.
- **Job fanout storms** — a bounded worker pool (default 6 workers) pulls from a single `asyncio.Queue`. When a large org bulk-imports 500 tickets, they queue up but only 6 run concurrently, keeping the event loop and thread pool healthy. No fake priority heuristic — real priority is determined by the LLM triage node inside the graph where it belongs.
- **Poison pills** — each `Job` tracks `retry_count` against a `max_retries` cap (default 3). On worker failure the job is re-enqueued with exponential backoff (`2^n` seconds). After all retries are exhausted it is marked `FAILED` and moved to a dead-letter queue (DLQ) visible at `GET /api/jobs/dlq`. Oversized bodies (>50 KB) are rejected at the HTTP layer with a 413 before they ever enter the queue.


## Setup

```bash
# Install dependencies
uv sync

# Copy env and add your API keys
cp .env.example .env

# Run the server
uv run uvicorn app.main:app --reload
```

Then open http://localhost:8000 in your browser.

## Tech Stack

- **LangGraph** — multi-agent orchestration
- **FastAPI** — API server
- **LangChain** — LLM abstractions, RAG
- **OpenRouter** — configurable LLM provider
