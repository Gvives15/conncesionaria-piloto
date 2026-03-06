from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class MotorRespondIn(BaseModel):
    tenant_id: str
    contact_key: str  # "wa:549..."
    wa_id: str
    phone_number_id: str
    turn_wamid: str
    text: Optional[str] = None

    # opcional: si querés que el LLM vea timestamp real del inbound
    timestamp_in: Optional[str] = None  # ISO string

    # opcional: pasar channel (default whatsapp)
    channel: str = "whatsapp"


class MotorDecision(BaseModel):
    primary_event: str
    secondary_events: List[str] = Field(default_factory=list)
    confidence: float = 0.0


class MotorPolicy(BaseModel):
    response_mode: str  # TEMPLATE | FREEFORM
    template_key: Optional[str] = None
    handoff: bool = False
    block: bool = False
    block_reason: Optional[str] = None


class MotorAction(BaseModel):
    type: str  # SEND_MESSAGE | CALL_TEXT_AI | HANDOFF
    channel: str = "whatsapp"

    # SEND_MESSAGE
    mode: Optional[str] = None  # template | freeform
    template_key: Optional[str] = None
    vars: Optional[Dict[str, Any]] = None
    text: Optional[str] = None

    # CALL_TEXT_AI (tu IA generadora de texto)
    prompt_key: Optional[str] = None
    input_json: Optional[Dict[str, Any]] = None

    # destinatario
    wa_id: Optional[str] = None
    phone_number_id: Optional[str] = None


class MemoryUpdate(BaseModel):
    active_primary_event: Optional[str] = None
    active_secondary_events: List[str] = Field(default_factory=list)
    recent_events: List[Dict[str, Any]] = Field(default_factory=list)
    scores_json: Dict[str, Any] = Field(default_factory=dict)
    summary: Optional[str] = None
    facts_json: List[Any] = Field(default_factory=list)


class MotorRespondOut(BaseModel):
    ok: bool = True
    tenant_id: str
    contact_key: str

    turn: Dict[str, Any]
    decision: MotorDecision
    policy: MotorPolicy
    next_actions: List[MotorAction] = Field(default_factory=list)

    memory_update: Optional[MemoryUpdate] = None
    telemetry: Dict[str, Any] = Field(default_factory=dict)
    warning: Optional[str] = None
