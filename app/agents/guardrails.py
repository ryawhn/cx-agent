from __future__ import annotations

from datetime import datetime, timezone

from langchain_core.messages import SystemMessage, HumanMessage

from app.llm import get_llm
from app.models import CXState, GuardrailResult

SYSTEM_PROMPT = """You are a compliance reviewer for a fintech CX team.
Review the draft response and check for these violations:

1. REFUND_TIMELINE: Promising specific refund timelines (e.g., "you'll receive your refund in 3 days")
2. INTERNAL_POLICY_LEAK: Sharing internal processes, system names, or policy details not meant for customers
3. UNAUTHORIZED_COMMITMENT: Making guarantees or promises the agent can't fulfill
4. PII_EXPOSURE: Including sensitive data that shouldn't be in the response
5. TONE_ISSUE: Dismissive, condescending, or unprofessional tone

If the draft passes all checks, set passed=true with an empty violations list.
If any violation is found, set passed=false, list the violations, and provide specific feedback on how to fix the draft."""


def guardrails_node(state: CXState) -> dict:
    draft = state["draft_response"]
    ticket = state["normalized_ticket"]

    llm = get_llm().with_structured_output(GuardrailResult)

    message = f"""Original ticket subject: {ticket['subject']}
Original ticket body: {ticket['body']}

Draft response to review:
{draft}"""

    result: GuardrailResult = llm.invoke([
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=message),
    ])

    return {
        "guardrail_result": result,
        "trace": [
            {
                "agent": "guardrails",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "output": result.model_dump(),
            }
        ],
    }


def guardrail_condition(state: CXState) -> str:
    from app.config import settings

    if state["guardrail_result"].passed:
        return "pass"
    if state.get("attempt", 1) >= settings.max_draft_attempts:
        return "pass"
    return "fail"
