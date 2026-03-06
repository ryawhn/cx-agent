from __future__ import annotations

from datetime import datetime, timezone

from langchain_core.messages import SystemMessage, HumanMessage

from app.llm import get_llm
from app.models import CXState, QAScores

SYSTEM_PROMPT = """You are a QA evaluator for fintech CX responses.
Score the draft response on three dimensions (1-10 each):

1. RELEVANCE: Does the response address the customer's specific issue? Does it use accurate information?
2. TONE: Is the tone empathetic, professional, and appropriate for the customer's sentiment?
3. COMPLIANCE: Does the response avoid prohibited content (refund promises, internal policy details, unauthorized commitments)?

Set passed=true if ALL scores are >= 7.
If any score is below 7, set passed=false and provide specific feedback on what needs improvement."""


def qa_eval_node(state: CXState) -> dict:
    draft = state["draft_response"]
    ticket = state["normalized_ticket"]
    triage = state["triage"]

    llm = get_llm().with_structured_output(QAScores)

    message = f"""Customer ticket:
Subject: {ticket['subject']}
Body: {ticket['body']}
Category: {triage.category.value}
Sentiment: {triage.sentiment.value}

Draft response:
{draft}"""

    result: QAScores = llm.invoke([
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=message),
    ])

    status = "completed" if result.passed else state.get("status", "processing")
    final = draft if result.passed else state.get("final_response", "")

    return {
        "qa_scores": result,
        "final_response": final,
        "status": status,
        "trace": [
            {
                "agent": "qa_eval",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "output": result.model_dump(),
            }
        ],
    }


def qa_condition(state: CXState) -> str:
    from app.config import settings

    if state["qa_scores"].passed:
        return "pass"
    if state.get("attempt", 1) >= settings.max_draft_attempts:
        return "pass"
    return "fail"
