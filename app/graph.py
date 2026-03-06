from __future__ import annotations

from datetime import datetime, timezone

from langgraph.graph import StateGraph, END

from app.models import CXState
from app.agents.intake import intake_node
from app.agents.triage import triage_node
from app.agents.router import router_node, route_condition
from app.agents.drafter import drafter_node
from app.agents.guardrails import guardrails_node, guardrail_condition
from app.agents.qa_eval import qa_eval_node, qa_condition


def _escalation_end(state: CXState) -> dict:
    return {
        "final_response": "",
        "status": "escalated",
        "trace": [
            {
                "agent": "end",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "output": {"reason": "Ticket escalated to human agent"},
            }
        ],
    }


def _finalize(state: CXState) -> dict:
    final = state.get("draft_response", "")
    return {
        "final_response": final,
        "status": "completed",
        "trace": [
            {
                "agent": "end",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "output": {"reason": "Response finalized"},
            }
        ],
    }


def build_graph() -> StateGraph:
    graph = StateGraph(CXState)

    graph.add_node("intake", intake_node)
    graph.add_node("triage", triage_node)
    graph.add_node("router", router_node)
    graph.add_node("drafter", drafter_node)
    graph.add_node("guardrails", guardrails_node)
    graph.add_node("qa_eval", qa_eval_node)
    graph.add_node("escalation_end", _escalation_end)
    graph.add_node("finalize", _finalize)

    graph.set_entry_point("intake")
    graph.add_edge("intake", "triage")
    graph.add_edge("triage", "router")

    graph.add_conditional_edges(
        "router",
        route_condition,
        {"escalate": "escalation_end", "draft": "drafter"},
    )

    graph.add_edge("drafter", "guardrails")

    graph.add_conditional_edges(
        "guardrails",
        guardrail_condition,
        {"pass": "qa_eval", "fail": "drafter"},
    )

    graph.add_conditional_edges(
        "qa_eval",
        qa_condition,
        {"pass": "finalize", "fail": "drafter"},
    )

    graph.add_edge("escalation_end", END)
    graph.add_edge("finalize", END)

    return graph.compile()


cx_graph = build_graph()
