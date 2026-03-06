from __future__ import annotations

from typing import List
from .schemas import Signals, SalesState, RouterDecision

def decide_playbook(
    signals: Signals,
    state: SalesState,
    window_open: bool
) -> RouterDecision:
    """
    CEREBRO DETERMINÍSTICO (ROUTER)
    
    Aplica la pirámide de prioridad de negocio:
    1. Riesgo / Safety
    2. Ventana cerrada
    3. Handoff explícito
    4. Objeciones
    5. Intención explícita
    6. Faltantes críticos
    7. Default
    """

    # 1. RIESGO / SAFETY (Prioridad Crítica)
    if signals.risk:
        return RouterDecision(
            playbook_key="SAFE_BOUNDARY",
            reason="Risk flag detected in signals.",
            priority_level=1
        )

    # 2. VENTANA CERRADA (Prioridad Técnica)
    if not window_open:
        return RouterDecision(
            playbook_key="REOPEN_24H",
            reason="WhatsApp 24h window is closed.",
            priority_level=1
        )

    # 3. HANDOFF (Prioridad Usuario)
    if signals.intent == "HANDOFF_REQUEST":
        return RouterDecision(
            playbook_key="HANDOFF",
            reason="User explicitly requested human agent.",
            priority_level=2
        )

    # 4. OBJECIONES (Bloqueo Comercial)
    if signals.objection:
        # Mapeo simple de objeciones a playbooks
        if "PRICE" in signals.objection.upper():
            return RouterDecision(
                playbook_key="OBJECTION_PRICE",
                reason=f"Handling price objection: {signals.objection}",
                priority_level=3
            )
        # TODO: Agregar más objeciones específicas (Stock, Financiación, etc.)
        # Por ahora default a handoff si es una objeción compleja no mapeada
        # O podríamos tener un GENERIC_OBJECTION
        return RouterDecision(
            playbook_key="HANDOFF", 
            reason=f"Unhandled objection: {signals.objection}",
            priority_level=3
        )

    # 5. INTENCIÓN EXPLÍCITA (Lo que el usuario pide YA)
    # Mapeo de intención -> Playbook
    intent_map = {
        "ASK_PRICE": "PRICE_QUOTE_MIN",
        "ASK_FINANCING": "FINANCING_MIN",
        "ASK_AVAILABILITY": "AVAILABILITY_MIN",
        "BOOK_TEST_DRIVE": "BOOK_VISIT",
        "SCHEDULE_VISIT": "BOOK_VISIT",
    }
    
    if signals.intent in intent_map:
        return RouterDecision(
            playbook_key=intent_map[signals.intent],
            reason=f"User intent '{signals.intent}' maps directly to playbook.",
            priority_level=4
        )

    # 6. FALTANTES CRÍTICOS (Proactividad del Vendedor)
    # Si no hay intención clara, miramos qué falta para avanzar
    if state.missing:
        # Prioridad de campos faltantes (orden importa)
        critical_fields = ["model", "budget", "timeframe"]
        
        # Si falta el modelo, es lo primero a resolver (Discovery)
        if "model" in state.missing:
             return RouterDecision(
                playbook_key="DISCOVERY_MIN",
                reason="Missing critical info: Vehicle Model.",
                priority_level=5
            )
        
        # Si falta presupuesto
        if "budget" in state.missing:
             return RouterDecision(
                playbook_key="DISCOVERY_MIN", # O un playbook específico de presupuesto
                reason="Missing critical info: Budget.",
                priority_level=5
            )

    # 7. DEFAULT / FALLBACK
    return RouterDecision(
        playbook_key="DEFAULT_ASSIST",
        reason="No specific rule triggered. Defaulting to assistance.",
        priority_level=6
    )
