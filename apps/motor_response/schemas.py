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


# --- NUEVOS CONTRATOS INTERNOS (PREIMPLEMENTACIÓN MOTOR HÍBRIDO) ---

class VehicleInterest(BaseModel):
    make: Optional[str] = None
    model: Optional[str] = None
    trim: Optional[str] = None
    year: Optional[str] = None
    new_or_used: Optional[str] = None


class CommercialInfo(BaseModel):
    budget: Optional[str] = None
    payment_type: Optional[str] = None
    timeframe: Optional[str] = None
    city: Optional[str] = None


class SalesState(BaseModel):
    """
    Estado comercial vivo del lead.
    Vive dentro de MemoryRecord.sales_state_json
    """
    stage: str = "discover"
    temperature: str = "warm"
    intent: str = "general"
    objection_primary: str = "none"
    missing: List[str] = Field(default_factory=list)
    next_action: str = "ask_model"
    lead_type: str = "new"
    
    vehicle: VehicleInterest = Field(default_factory=VehicleInterest)
    commercial: CommercialInfo = Field(default_factory=CommercialInfo)


class Signals(BaseModel):
    """
    Salida pura del Extractor (Ojos).
    No decide nada, solo estructura lo que vio.
    """
    intent: str
    objection: Optional[str] = None  # Mapped from objection_primary
    risk: bool = False               # Mapped from risk_flag
    entities: Dict[str, Any] = Field(default_factory=dict)


class PlaybookConfig(BaseModel):
    """
    Configuración estática de una jugada comercial.
    """
    id: str
    goal: str
    style_rules: str
    required_actions: List[Dict[str, Any]] = Field(default_factory=list)
    force_template: Optional[str] = None


class RouterDecision(BaseModel):
    """
    Decisión final del Router (Cerebro).
    """
    playbook_key: str
    reason: str
    priority_level: int


# --- CONTRATOS OFICIALES DE NEXT_ACTIONS (HÍBRIDO) ---

class CallTextAIPayload(BaseModel):
    """
    Payload específico para la acción CALL_TEXT_AI del Motor Híbrido.
    Diseñado para alimentar al Drafter (Redactor).
    """
    playbook_id: str
    objective: str
    copy_rules: List[str] = Field(default_factory=list) # Renamed from style_rules, and normalized to list
    sales_state: Dict[str, Any]
    signals: Dict[str, Any]
    context_summary: str
    question_limit: int = 1
    cta_type: str = "open" # "open", "specific", "none"


class HandoffPayload(BaseModel):
    """
    Payload específico para HANDOFF_TO_HUMAN.
    """
    reason: str
    department: Optional[str] = None
    priority: str = "normal"


