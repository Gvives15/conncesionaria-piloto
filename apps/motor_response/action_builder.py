from __future__ import annotations

from typing import Any, Dict, List, Optional
from .schemas import (
    MotorRespondIn, PlaybookConfig, SalesState, Signals,
    CallTextAIPayload, HandoffPayload
)

def build_actions_from_playbook(
    payload: MotorRespondIn,
    playbook: Optional[PlaybookConfig],
    state: SalesState,
    signals: Signals
) -> List[Dict[str, Any]]:
    """
    Construye las next_actions del Motor Vendedor Híbrido.
    Genera acciones semánticas normalizadas.
    
    CATÁLOGO OFICIAL:
    - CALL_TEXT_AI (Generativo)
    - SEND_TEMPLATE (Estático)
    - HANDOFF_TO_HUMAN (Control)
    """
    
    # 1. Fallback si no hay playbook (Safety net)
    if not playbook:
        return []

    actions = []

    # 2. Acciones requeridas por el Playbook (ej: HANDOFF)
    for req_action in playbook.required_actions:
        # Normalización de HANDOFF
        if req_action.get("type") == "HANDOFF":
            handoff_payload = HandoffPayload(
                reason=req_action.get("reason", "PLAYBOOK_REQUIRED"),
                department=req_action.get("department"),
                priority=req_action.get("priority", "normal")
            )
            
            actions.append({
                "type": "HANDOFF_TO_HUMAN",
                "channel": payload.channel,
                "payload": handoff_payload.model_dump(),
                "wa_id": payload.wa_id,
                "phone_number_id": payload.phone_number_id,
            })
        else:
            # Otras acciones técnicas se pasan as-is pero con IDs inyectados
            ax = req_action.copy()
            ax["wa_id"] = payload.wa_id
            ax["phone_number_id"] = payload.phone_number_id
            actions.append(ax)

    # 3. Acción de Comunicación (Template vs Generativo)
    
    # CASO A: Template Forzado (Ventana cerrada o Safety)
    if playbook.force_template:
        template_action = {
            "type": "SEND_TEMPLATE",  # Nombre oficial normalizado
            "channel": payload.channel,
            "template_key": playbook.force_template,
            "vars": {},
            "wa_id": payload.wa_id,
            "phone_number_id": payload.phone_number_id,
        }
        actions.append(template_action)
        
    # CASO B: Generación de Texto (Freeform con instrucciones)
    else:
        # Construimos el payload OFICIAL para el Drafter
        gen_payload = CallTextAIPayload(
            playbook_id=playbook.id,
            objective=playbook.goal,
            style_rules=playbook.style_rules,
            sales_state=state.model_dump(),
            signals=signals.model_dump(),
            context_summary=f"User intends to {signals.intent}. Missing: {state.missing}. Next: {state.next_action}",
            question_limit=1,
            copy_rules=[]
        )

        text_ai_action = {
            "type": "CALL_TEXT_AI",
            "channel": payload.channel,
            "prompt_key": "DRAFTER_V1", 
            "input_json": gen_payload.model_dump(),
            "wa_id": payload.wa_id,
            "phone_number_id": payload.phone_number_id,
        }
        actions.append(text_ai_action)

    return actions
