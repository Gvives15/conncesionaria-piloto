from __future__ import annotations

from typing import Any, Dict, List, Optional
from .schemas import MotorRespondIn, PlaybookConfig, SalesState, Signals

def build_actions_from_playbook(
    payload: MotorRespondIn,
    playbook: Optional[PlaybookConfig],
    state: SalesState,
    signals: Signals
) -> List[Dict[str, Any]]:
    """
    Construye las next_actions del Motor Vendedor Híbrido.
    Genera acciones semánticas (CALL_TEXT_AI, SEND_TEMPLATE, HANDOFF) 
    basadas en la estrategia del Playbook y el estado comercial.
    """
    
    # 1. Fallback si no hay playbook (Safety net)
    if not playbook:
        return []

    actions = []

    # 2. Acciones requeridas por el Playbook (ej: HANDOFF, CRM_UPDATE)
    # Estas son acciones técnicas o de control que siempre deben ocurrir
    for req_action in playbook.required_actions:
        # Copiamos para no mutar config estática
        ax = req_action.copy()
        
        # Inyectamos IDs de contexto
        ax["wa_id"] = payload.wa_id
        ax["phone_number_id"] = payload.phone_number_id
        
        # Mapeo específico para HANDOFF
        if ax.get("type") == "HANDOFF":
            # Aseguramos formato compatible con orquestador
            ax["channel"] = payload.channel
            # Si no tiene reason, ponemos default
            if "reason" not in ax: ax["reason"] = "PLAYBOOK_REQUIRED"
            
        actions.append(ax)

    # 3. Acción de Comunicación (Template vs Generativo)
    
    # CASO A: Template Forzado (Ventana cerrada o Safety)
    if playbook.force_template:
        template_action = {
            "type": "SEND_MESSAGE",
            "channel": payload.channel,
            "mode": "template",
            "template_key": playbook.force_template,
            "vars": {},  # TODO: Podríamos inyectar vars del state (ej: name)
            "wa_id": payload.wa_id,
            "phone_number_id": payload.phone_number_id,
        }
        actions.append(template_action)
        
    # CASO B: Generación de Texto (Freeform con instrucciones)
    else:
        # Construimos el payload rico para el "Drafter" (Redactor)
        gen_input = {
            "playbook_id": playbook.id,
            "objective": playbook.goal,
            "style_rules": playbook.style_rules,
            "sales_state": state.model_dump(),
            "signals": signals.model_dump(),
            "context_summary": f"User intends to {signals.intent}. Missing: {state.missing}. Next: {state.next_action}"
        }

        text_ai_action = {
            "type": "CALL_TEXT_AI",
            "channel": payload.channel,
            "prompt_key": "DRAFTER_V1", # Prompt ID conceptual para el redactor
            "input_json": gen_input,
            "wa_id": payload.wa_id,
            "phone_number_id": payload.phone_number_id,
        }
        actions.append(text_ai_action)

    return actions
