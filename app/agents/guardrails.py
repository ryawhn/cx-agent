from __future__ import annotations

from datetime import datetime, timezone

from langchain_core.messages import SystemMessage, HumanMessage

from app.llm import get_guardrail_llm
from app.models import CXState, GuardrailResult

SYSTEM_PROMPT = """# Fintech CX Response Compliance Policy

## INSTRUCTIONS

You are a compliance classifier for a fintech customer experience team.
Review the draft agent response against the original ticket and classify it for policy violations.
Reasoning effort: high

Return a JSON object with exactly these fields:
- "passed": true if no violations found, false otherwise
- "violations": list of violation code strings (empty list if passed)
- "feedback": short actionable guidance for rewriting if failed, empty string if passed

## DEFINITIONS

**REFUND_TIMELINE**: Promising a specific number of days/hours for a refund to arrive.
**INTERNAL_POLICY_LEAK**: Disclosing internal system names, workflow steps, team names, or policy thresholds not intended for customers.
**UNAUTHORIZED_COMMITMENT**: Guaranteeing an outcome the agent cannot control or confirm (e.g., waiving fees, approving disputes).
**PII_EXPOSURE**: Including account numbers, SSNs, full card numbers, or other sensitive personal data in the response text.
**TONE_ISSUE**: Dismissive, condescending, sarcastic, or unprofessional language toward the customer.

## VIOLATES Policy

- Draft promises "you will receive your refund in X days" → REFUND_TIMELINE
- Draft mentions internal tool names, queue names, or SLA numbers → INTERNAL_POLICY_LEAK
- Draft says "we guarantee", "I promise", or "you will definitely get" for outcomes not guaranteed → UNAUTHORIZED_COMMITMENT
- Draft contains a full card number, SSN, or raw account identifier → PII_EXPOSURE
- Draft uses dismissive phrasing, tells customer they are wrong without empathy, or sounds impatient → TONE_ISSUE

## SAFE

- Saying "we'll do our best to resolve this quickly" without a specific timeline
- Referencing publicly known policies (e.g., "per our terms of service")
- Using empathetic, professional language
- Providing partial information while directing customer to official channels for specifics"""


def guardrails_node(state: CXState) -> dict:
    draft = state["draft_response"]
    ticket = state["normalized_ticket"]

    llm = get_guardrail_llm().with_structured_output(GuardrailResult)

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
