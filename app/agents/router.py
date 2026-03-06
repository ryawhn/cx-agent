from __future__ import annotations

from datetime import datetime, timezone

from app.models import CXState, Route, Urgency, Sentiment, Category


def router_node(state: CXState) -> dict:
    triage = state["triage"]
    urgency = triage.urgency
    sentiment = triage.sentiment
    category = triage.category

    if urgency == Urgency.P1 and sentiment in (Sentiment.ANGRY, Sentiment.FRUSTRATED):
        route = Route.ESCALATE
    elif urgency == Urgency.P1:
        route = Route.DRAFT_FOR_REVIEW
    elif urgency == Urgency.P3 and sentiment in (Sentiment.NEUTRAL, Sentiment.POSITIVE) and category == Category.GENERAL:
        route = Route.AUTO_RESPOND
    else:
        route = Route.DRAFT_FOR_REVIEW

    status = "escalated" if route == Route.ESCALATE else "processing"

    return {
        "route": route.value,
        "status": status,
        "trace": [
            {
                "agent": "router",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "output": {
                    "route": route.value,
                    "reason": _route_reason(urgency, sentiment, category, route),
                },
            }
        ],
    }


def route_condition(state: CXState) -> str:
    if state["route"] == Route.ESCALATE.value:
        return "escalate"
    return "draft"


def _route_reason(urgency, sentiment, category, route) -> str:
    if route == Route.ESCALATE:
        return f"{urgency.value} urgency with {sentiment.value} sentiment — requires human escalation"
    if route == Route.AUTO_RESPOND:
        return f"{urgency.value} urgency, {sentiment.value} sentiment, {category.value} category — safe for auto-response"
    return f"{urgency.value} urgency — draft response for human review"
