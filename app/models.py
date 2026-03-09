from __future__ import annotations

from enum import Enum
from typing import Annotated

from pydantic import BaseModel, Field
from typing_extensions import TypedDict

import operator


# --- Enums ---

class Urgency(str, Enum):
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class Category(str, Enum):
    BILLING = "billing"
    CARD_ISSUE = "card_issue"
    PAYMENT = "payment"
    KYC = "kyc"
    GENERAL = "general"


class Sentiment(str, Enum):
    ANGRY = "angry"
    FRUSTRATED = "frustrated"
    NEUTRAL = "neutral"
    POSITIVE = "positive"


class Route(str, Enum):
    AUTO_RESPOND = "auto_respond"
    DRAFT_FOR_REVIEW = "draft_for_review"
    ESCALATE = "escalate"


# --- Structured output models (returned by LLM) ---

class TriageResult(BaseModel):
    urgency: Urgency = Field(description="Ticket urgency: P1 (critical), P2 (high), P3 (normal)")
    category: Category = Field(description="Ticket category")
    sentiment: Sentiment = Field(description="Customer sentiment")
    reasoning: str = Field(description="Brief explanation of the classification")


class GuardrailResult(BaseModel):
    passed: bool = Field(description="Whether the draft passes all compliance checks")
    violations: list[str] = Field(default_factory=list, description="List of compliance violations found")
    feedback: str = Field(default="", description="Feedback for rewriting if failed")


class QAScores(BaseModel):
    relevance: int = Field(ge=1, le=10, description="How relevant the response is to the ticket (1-10)")
    tone: int = Field(ge=1, le=10, description="How appropriate the tone is (1-10)")
    compliance: int = Field(ge=1, le=10, description="How compliant the response is (1-10)")
    passed: bool = Field(description="Whether all scores meet the threshold (>= 7)")
    feedback: str = Field(default="", description="Feedback for improvement if failed")


# --- Graph state ---

class CXState(TypedDict):
    ticket: dict
    normalized_ticket: dict
    triage: TriageResult | None
    route: str
    context_docs: list[str]
    draft_response: str
    guardrail_result: GuardrailResult | None
    qa_scores: QAScores | None
    attempt: int
    final_response: str
    status: str
    trace: Annotated[list[dict], operator.add]


# --- API request/response ---

class TicketRequest(BaseModel):
    customer_name: str = ""
    customer_email: str = ""
    subject: str
    body: str
    channel: str = "email"
    metadata: dict = Field(default_factory=dict)


class ProcessResponse(BaseModel):
    ticket_id: str
    status: str
    triage: TriageResult | None = None
    route: str = ""
    final_response: str = ""
    guardrail_result: GuardrailResult | None = None
    qa_scores: QAScores | None = None
    trace: list[dict] = Field(default_factory=list)


class JobResponse(BaseModel):
    job_id: str
    status: str
    created_at: str
    updated_at: str
    result: ProcessResponse | None = None
    error: str | None = None
