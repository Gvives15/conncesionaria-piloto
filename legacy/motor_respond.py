"""
Motor Respond module

This module implements a minimal event classification and response policy for a multi‑tenant mini motor
designed to handle WhatsApp inbound messages for a small business, such as a cigarette distributor.

It defines a set of common events, scoring rules based on keywords, and generates a structured
``event pack`` JSON object describing how the system should respond to a given message. The logic
enforces the 24‑hour reply window: if more than 24 hours have elapsed since the last message from
the customer, the system must use a pre‑approved template (to respect WhatsApp policy). Otherwise
it may respond freely (freeform).

Usage example::

    from motor_respond import generate_event_pack
    last_ts = datetime.utcnow() - timedelta(hours=1)
    pack = generate_event_pack(
        tenant_id="distri_cig_001",
        contact_key="wa:5493510000000",
        wa_id="5493510000000",
        phone_number_id="TEST_PHONE",
        turn_wamid="wamid.TEST.1",
        text="hola, cuanto sale marlboro box?",
        last_user_message_at=last_ts,
    )
    # send pack['next_actions'] to your orchestrator

You can integrate this function into your Django Ninja API at ``/v1/motor/respond``. It returns a
dictionary matching the event pack schema described in the system design notes.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple


# Define the list of events and their corresponding keyword triggers with associated points.
# These events are generic enough to cover a cigarette distributor but can be extended for other
# domains. Each event has a ``max_points`` used to normalise confidence scores.

EVENT_DEFINITIONS: Dict[str, Dict[str, object]] = {
    "SALUDO": {
        "max_points": 10,
        "triggers": [
            ("hola", 3), ("buenos", 2), ("buenas", 2), ("qué tal", 2), ("que tal", 2),
        ],
    },
    "PEDIDO": {
        "max_points": 15,
        "triggers": [
            ("quiero", 3), ("necesito", 3), ("mandame", 4), ("mandar", 3), ("pedido", 5),
        ],
    },
    "CONSULTA_PRECIO_PROMO": {
        "max_points": 18,
        "triggers": [
            ("precio", 5), ("lista", 4), ("promo", 4), ("oferta", 4), ("cuanto", 3),
            ("vale", 3), ("cuesta", 3),
        ],
    },
    "DISPONIBILIDAD_STOCK": {
        "max_points": 15,
        "triggers": [
            ("tenes", 4), ("tenés", 4), ("hay", 3), ("stock", 5), ("disponible", 5), ("queda", 2),
        ],
    },
    "ENVIO_ENTREGA": {
        "max_points": 16,
        "triggers": [
            ("envio", 5), ("envío", 5), ("reparto", 5), ("entrega", 4), ("llegan", 4), ("cuando", 2),
        ],
    },
    "MEDIOS_DE_PAGO": {
        "max_points": 15,
        "triggers": [
            ("transferencia", 5), ("efectivo", 4), ("tarjeta", 4), ("mp", 3), ("mercado pago", 3), ("factura", 3),
        ],
    },
    "CUENTA_CORRIENTE_CREDITO": {
        "max_points": 18,
        "triggers": [
            ("cuenta corriente", 6), ("fiado", 6), ("saldo", 4), ("limite", 4), ("límite", 4), ("credito", 4), ("crédito", 4),
        ],
    },
    "RECLAMO": {
        "max_points": 20,
        "triggers": [
            ("reclamo", 6), ("faltó", 5), ("falto", 5), ("no llegó", 5), ("no llego", 5), ("vino mal", 5), ("error", 4), ("devolución", 4), ("devolucion", 4),
        ],
    },
}


def _score_event(text: str, event_name: str) -> int:
    """Compute the score for a given event by summing the points of matched keywords."""
    definition = EVENT_DEFINITIONS.get(event_name, {})
    score = 0
    for kw, pts in definition.get("triggers", []):
        if kw in text:
            score += pts
    return score


def detect_event(text: str) -> Tuple[str, float, Dict[str, int]]:
    """Return the most likely event name, its confidence score (0–1), and per‑event scores.

    :param text: Lowercase input text.
    :returns: (chosen_event, confidence, scores_dict)
    """
    scores: Dict[str, int] = {}
    for event_name in EVENT_DEFINITIONS:
        scores[event_name] = _score_event(text, event_name)

    # Choose the event with the highest score; if all zero, fallback to SALUDO or GENERIC_CLARIFY
    chosen_event = max(scores, key=lambda e: scores[e])
    max_score = scores[chosen_event]
    max_points = EVENT_DEFINITIONS[chosen_event]["max_points"]
    confidence = float(max_score) / max_points if max_points else 0.0

    return chosen_event, confidence, scores


def generate_event_pack(
    tenant_id: str,
    contact_key: str,
    wa_id: str,
    phone_number_id: str,
    turn_wamid: str,
    text: Optional[str],
    last_user_message_at: Optional[datetime],
    now: Optional[datetime] = None,
) -> Dict[str, object]:
    """Generate an Event Pack dict for the mini motor.

    :param tenant_id: Identificador del negocio
    :param contact_key: Clave de contacto (ej. "wa:549...")
    :param wa_id: Número WhatsApp del destinatario
    :param phone_number_id: ID del número de WhatsApp Business para respuestas
    :param turn_wamid: ID del mensaje entrante
    :param text: Texto del mensaje entrante (opcional)
    :param last_user_message_at: Último timestamp de mensaje del usuario (timezone aware)
    :param now: Tiempo actual (si None, usa datetime.utcnow())
    :returns: Diccionario con la decisión y acciones a tomar
    """
    if now is None:
        now = datetime.utcnow()
    reply_text = ""
    text_lower = (text or "").lower()

    # Determine whether the conversation is within the 24 hour window
    window_open = True
    if last_user_message_at:
        window_open = (now - last_user_message_at) <= timedelta(hours=24)

    # 24h closed: send reopen template
    if not window_open:
        return {
            "ok": True,
            "tenant_id": tenant_id,
            "contact_key": contact_key,
            "turn": {
                "turn_wamid": turn_wamid,
                "text_in": text,
            },
            "decision": {
                "event": "REOPEN_WINDOW",
                "confidence": 1.0,
            },
            "policy": {
                "response_mode": "TEMPLATE",
                "template_key": "REOPEN_24H",
                "handoff": False,
                "block": False,
                "block_reason": None,
            },
            "next_actions": [
                {
                    "type": "SEND_MESSAGE",
                    "channel": "whatsapp",
                    "mode": "template",
                    "template_key": "REOPEN_24H",
                    "vars": {},
                    "wa_id": wa_id,
                    "phone_number_id": phone_number_id,
                }
            ],
            "telemetry": {"window_open": window_open},
        }

    # Run safety check for inappropriate language (very basic): block if insults or offensive words
    offensive_words = ["puta", "mierda", "idiota", "estafa"]
    if any(w in text_lower for w in offensive_words):
        return {
            "ok": True,
            "tenant_id": tenant_id,
            "contact_key": contact_key,
            "turn": {
                "turn_wamid": turn_wamid,
                "text_in": text,
            },
            "decision": {
                "event": "SAFETY_BLOCK",
                "confidence": 1.0,
            },
            "policy": {
                "response_mode": "TEMPLATE",
                "template_key": "SAFE_BOUNDARY",
                "handoff": True,
                "block": True,
                "block_reason": "INAPPROPRIATE_LANGUAGE",
            },
            "next_actions": [
                {
                    "type": "SEND_MESSAGE",
                    "channel": "whatsapp",
                    "mode": "template",
                    "template_key": "SAFE_BOUNDARY",
                    "vars": {},
                    "wa_id": wa_id,
                    "phone_number_id": phone_number_id,
                }
            ],
            "telemetry": {"window_open": window_open},
        }

    # Otherwise classify the event
    chosen_event, confidence, score_details = detect_event(text_lower)

    # Determine base policy and handoff
    policy = {
        "response_mode": "FREEFORM",
        "template_key": None,
        "handoff": False,
        "block": False,
        "block_reason": None,
    }

    # Default reply prompts for each event (freeform)
    freeform_replies = {
        "SALUDO": "¡Hola! ¿En qué puedo ayudarte? ¿Precio, pedido, stock, envío, pago, cuenta corriente o reclamos?",
        "PEDIDO": "Entendido. ¿Qué productos necesitás y cuántos? Especificá las marcas y cantidades, por favor.",
        "CONSULTA_PRECIO_PROMO": "Claro, ¿de qué marca y presentación estás consultando el precio? Podés mencionar box o suelto.",
        "DISPONIBILIDAD_STOCK": "Para verificar disponibilidad, indicá la marca de cigarrillos y la cantidad que buscás.",
        "ENVIO_ENTREGA": "¿En qué zona estás y para cuándo necesitás recibir el pedido?", 
        "MEDIOS_DE_PAGO": "Podés pagar en efectivo o transferencia. ¿Cuál preferís?", 
        "CUENTA_CORRIENTE_CREDITO": "Por favor, indicá tu nombre o el del kiosco y CUIT o teléfono para revisar tu cuenta corriente.",
        "RECLAMO": "Lamento lo ocurrido. Ya derivamos tu reclamo a un asesor para que te contacte.",
    }

    # Templates (approved names) per event if you want to send templates within 24h; can be extended.
    template_keys = {
        "SALUDO": "SALUDO_24H",
        "PEDIDO": "PEDIDO_ASK",
        "CONSULTA_PRECIO_PROMO": "PRECIO_ASK",
        "DISPONIBILIDAD_STOCK": "STOCK_ASK",
        "ENVIO_ENTREGA": "ENVIO_ASK",
        "MEDIOS_DE_PAGO": "PAGO_INFO",
        "CUENTA_CORRIENTE_CREDITO": "CUENTA_HANDOFF",
        "RECLAMO": "RECLAMO_HANDOFF",
        "REOPEN_WINDOW": "REOPEN_24H",
        "SAFETY_BLOCK": "SAFE_BOUNDARY",
    }

    # Handoff rule: always handoff for RECLAMO and CUENTA events
    if chosen_event in {"RECLAMO", "CUENTA_CORRIENTE_CREDITO"}:
        policy["handoff"] = True

    # Low confidence fallback
    if confidence < 0.45:
        chosen_event = "SALUDO"
        confidence = 0.4
        reply_text = freeform_replies[chosen_event]
    else:
        reply_text = freeform_replies.get(chosen_event, freeform_replies["SALUDO"])

    # Determine final response mode: if you prefer templates even within window,
    # you can override here. For this MVP, we use freeform when window is open.
    response_mode = "FREEFORM"
    template_key = None
    if policy.get("handoff"):
        # For handoff events, use template only
        response_mode = "TEMPLATE"
        template_key = template_keys.get(chosen_event)
    else:
        # If you want to use templates always for this event type, set here
        # e.g. for PAYMENT use template
        response_mode = "FREEFORM"

    policy["response_mode"] = response_mode
    policy["template_key"] = template_key

    next_actions: List[Dict[str, object]] = []

    if response_mode == "TEMPLATE":
        next_actions.append({
            "type": "SEND_MESSAGE",
            "channel": "whatsapp",
            "mode": "template",
            "template_key": template_key,
            "vars": {},
            "wa_id": wa_id,
            "phone_number_id": phone_number_id,
        })
    else:  # FREEFORM
        # In a real system you might first call a language model to generate a custom answer.
        # For MVP, we send the static reply_text.
        next_actions.append({
            "type": "SEND_MESSAGE",
            "channel": "whatsapp",
            "mode": "freeform",
            "text": reply_text,
            "wa_id": wa_id,
            "phone_number_id": phone_number_id,
        })

    return {
        "ok": True,
        "tenant_id": tenant_id,
        "contact_key": contact_key,
        "turn": {
            "turn_wamid": turn_wamid,
            "text_in": text,
        },
        "decision": {
            "event": chosen_event,
            "confidence": round(confidence, 2),
        },
        "policy": policy,
        "next_actions": next_actions,
        "telemetry": {
            "window_open": window_open,
            "scores": score_details,
        },
    }


__all__ = ["generate_event_pack", "EVENT_DEFINITIONS"]