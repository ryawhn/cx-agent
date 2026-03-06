from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone

from app.models import CXState


def intake_node(state: CXState) -> dict:
    ticket = state["ticket"]

    subject = _clean_text(ticket.get("subject", ""))
    body = _clean_text(ticket.get("body", ""))

    normalized = {
        "ticket_id": ticket.get("id") or f"TKT-{uuid.uuid4().hex[:8].upper()}",
        "customer_name": ticket.get("customer_name", "Unknown"),
        "customer_email": ticket.get("customer_email", ""),
        "subject": subject,
        "body": body,
        "channel": ticket.get("channel", "email"),
        "metadata": ticket.get("metadata", {}),
        "received_at": datetime.now(timezone.utc).isoformat(),
    }

    return {
        "normalized_ticket": normalized,
        "status": "processing",
        "attempt": 0,
        "trace": [
            {
                "agent": "intake",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "output": {
                    "ticket_id": normalized["ticket_id"],
                    "subject": normalized["subject"],
                    "channel": normalized["channel"],
                },
            }
        ],
    }


def _clean_text(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text
