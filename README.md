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
