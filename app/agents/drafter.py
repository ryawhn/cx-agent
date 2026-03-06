from __future__ import annotations

from datetime import datetime, timezone

from langchain_core.messages import SystemMessage, HumanMessage

from app.llm import get_llm
from app.knowledge.rag import retrieve
from app.models import CXState

SYSTEM_PROMPT = """You are a professional CX response writer for a fintech company.
Write a helpful, empathetic response to the customer's support ticket using the provided knowledge base context.

Guidelines:
- Be empathetic and professional, acknowledge the customer's frustration if applicable
- Use the knowledge base context to provide accurate information
- NEVER promise specific refund timelines or amounts
- NEVER share internal policies, processes, or system details
- NEVER make commitments you can't guarantee (e.g., "your refund will arrive in 3 days")
- Use phrases like "typically", "generally", "our team will review" instead of guarantees
- Keep the response concise (3-6 sentences)
- Address the customer by name if available
- Sign off professionally

{feedback_section}"""


def drafter_node(state: CXState) -> dict:
    ticket = state["normalized_ticket"]
    triage = state["triage"]
    attempt = state.get("attempt", 0) + 1

    query = f"{ticket['subject']} {ticket['body']}"
    context_docs = retrieve(query, k=3)

    feedback_section = ""
    if attempt > 1:
        guardrail = state.get("guardrail_result")
        qa = state.get("qa_scores")
        feedback_parts = []
        if guardrail and not guardrail.passed:
            feedback_parts.append(f"Compliance feedback: {guardrail.feedback}")
        if qa and not qa.passed:
            feedback_parts.append(f"Quality feedback: {qa.feedback}")
        if feedback_parts:
            feedback_section = "IMPORTANT — Fix these issues from the previous draft:\n" + "\n".join(feedback_parts)

    system = SYSTEM_PROMPT.format(feedback_section=feedback_section)

    message = f"""Customer: {ticket.get('customer_name', 'Customer')}
Subject: {ticket['subject']}
Message: {ticket['body']}
Category: {triage.category.value}
Urgency: {triage.urgency.value}
Sentiment: {triage.sentiment.value}

Knowledge Base Context:
{chr(10).join(f'---{chr(10)}{doc}{chr(10)}' for doc in context_docs)}"""

    llm = get_llm()
    response = llm.invoke([
        SystemMessage(content=system),
        HumanMessage(content=message),
    ])

    return {
        "context_docs": context_docs,
        "draft_response": response.content,
        "attempt": attempt,
        "trace": [
            {
                "agent": "drafter",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "output": {
                    "attempt": attempt,
                    "context_docs_count": len(context_docs),
                    "draft_preview": response.content[:200] + "..." if len(response.content) > 200 else response.content,
                },
            }
        ],
    }
