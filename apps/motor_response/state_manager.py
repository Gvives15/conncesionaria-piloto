from __future__ import annotations

from typing import List, Optional
from .schemas import SalesState, Signals, VehicleInterest, CommercialInfo

def update_sales_state(current: SalesState, signals: Signals) -> SalesState:
    """
    Actualiza el estado comercial basado en nuevas señales.
    Aplica lógica de merge, recálculo de missing y determinación de next_action.
    """
    # 1. Copia base para no mutar in-place accidentalmente
    new_state = current.model_copy(deep=True)

    # 2. Actualizar Intent (A. Intent)
    if signals.intent and signals.intent not in ["OTHER", "GENERAL"]:
        new_state.intent = signals.intent
    elif not new_state.intent:
        new_state.intent = "general"

    # 3. Actualizar Objeción (B. Objeción)
    if signals.objection:
        new_state.objection_primary = signals.objection
    # Si no hay objeción nueva, mantenemos la anterior (sticky) o podríamos limpiarla
    # Regla MVP: Sticky hasta que se resuelva (pero aquí solo hacemos merge simple)

    # 4. Merge Entities (C. Vehicle / Commercial)
    extracted_vehicle = signals.entities.get("vehicle") or {}
    if extracted_vehicle:
        # Solo actualizamos si el valor no es nulo
        for k, v in extracted_vehicle.items():
            if v and hasattr(new_state.vehicle, k):
                setattr(new_state.vehicle, k, v)

    extracted_commercial = signals.entities.get("commercial") or {}
    if extracted_commercial:
        for k, v in extracted_commercial.items():
            if v and hasattr(new_state.commercial, k):
                setattr(new_state.commercial, k, v)

    # 5. Recalcular Missing (D. Missing)
    # Definición de campos críticos
    missing_fields = []
    
    # Vehicle criticals
    if not new_state.vehicle.model:
        missing_fields.append("vehicle.model")
    if not new_state.vehicle.new_or_used:
        missing_fields.append("vehicle.new_or_used")
        
    # Commercial criticals
    if not new_state.commercial.city:
        missing_fields.append("commercial.city")
    
    # Budget es crítico si la intención es precio/financiación
    is_price_intent = new_state.intent in ["ASK_PRICE", "ASK_FINANCING", "PRICE_QUOTE_MIN"]
    if is_price_intent and not new_state.commercial.budget:
        missing_fields.append("commercial.budget")

    new_state.missing = missing_fields

    # 6. Recalcular Next Action (E. next_action)
    if "vehicle.model" in missing_fields:
        new_state.next_action = "ask_model"
    elif "vehicle.new_or_used" in missing_fields:
        new_state.next_action = "ask_new_or_used"
    elif "commercial.city" in missing_fields:
        new_state.next_action = "ask_city"
    elif "commercial.budget" in missing_fields:
        new_state.next_action = "ask_budget"
    else:
        new_state.next_action = "send_options"

    # 7. Recalcular Stage (F. stage)
    # Regla simple basada en missing count
    missing_count = len(missing_fields)
    
    if missing_count >= 3:
        new_state.stage = "discover"
    elif missing_count >= 1:
        new_state.stage = "qualify"
    else:
        new_state.stage = "offer"

    return new_state
