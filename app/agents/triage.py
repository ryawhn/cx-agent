from __future__ import annotations

from datetime import datetime, timezone

from langchain_core.messages import SystemMessage, HumanMessage

from app.llm import get_llm
from app.models import CXState, TriageResult

SYSTEM_PROMPT = """You are a CX ticket triage specialist for a fintech company.
Analyze the support ticket and classify it.

Urgency levels:
- P1 (critical): account locked, fraud/unauthorized transactions, payment failures > $500, security breaches
- P2 (high): billing disputes, KYC rejections, card issues affecting transactions, failed payments < $500
- P3 (normal): general inquiries, fee questions, account upgrades, minor app issues

Categories: billing, card_issue, payment, kyc, general

Sentiment: angry (hostile/threatening language), frustrated (clearly upset but civil), neutral (matter-of-fact), positive (polite/appreciative)

Respond with your classification and brief reasoning."""


def triage_node(state: CXState) -> dict:
    ticket = state["normalized_ticket"]
    llm = get_llm().with_structured_output(TriageResult)

    message = f"""Ticket ID: {ticket['ticket_id']}
Subject: {ticket['subject']}
Body: {ticket['body']}
Channel: {ticket['channel']}
Metadata: {ticket.get('metadata', {})}"""

    result: TriageResult = llm.invoke([
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=message),
    ])

    return {
        "triage": result,
        "trace": [
            {
                "agent": "triage",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "output": result.model_dump(),
            }
        ],
    }
