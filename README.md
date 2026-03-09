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

## Edge Cases Consideration


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
