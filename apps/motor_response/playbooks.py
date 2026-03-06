from __future__ import annotations

from typing import Dict, Optional
from .schemas import PlaybookConfig

# --- PLAYBOOK REGISTRY ---
# Este archivo contiene las "recetas" comerciales estáticas.
# No hay lógica aquí, solo configuración.

PLAYBOOK_REGISTRY: Dict[str, PlaybookConfig] = {
    # --- RIESGO Y CONTROL ---
    "SAFE_BOUNDARY": PlaybookConfig(
        id="SAFE_BOUNDARY",
        goal="Block inappropriate content and set boundaries.",
        style_rules="Firm, polite, and professional. Do not engage with the offensive content.",
        required_actions=[{"type": "HANDOFF", "reason": "SAFETY_BLOCK"}],
        force_template="SAFE_BOUNDARY"
    ),
    "REOPEN_24H": PlaybookConfig(
        id="REOPEN_24H",
        goal="Re-engage the user after 24h window closed.",
        style_rules="Use template only.",
        required_actions=[],
        force_template="REOPEN_24H"
    ),
    "HANDOFF": PlaybookConfig(
        id="HANDOFF",
        goal="Transfer the conversation to a human agent.",
        style_rules="Polite and reassuring. Confirm that a human will attend shortly.",
        required_actions=[{"type": "HANDOFF", "reason": "USER_REQUEST"}],
        force_template="HANDOFF_GENERIC"
    ),

    # --- JUGADAS COMERCIALES ---
    "DISCOVERY_MIN": PlaybookConfig(
        id="DISCOVERY_MIN",
        goal="Identify the vehicle model and key needs.",
        style_rules="Helpful and inquisitive. Ask one clear question at a time.",
        required_actions=[]
    ),
    "PRICE_QUOTE_MIN": PlaybookConfig(
        id="PRICE_QUOTE_MIN",
        goal="Provide a price estimate or range for the requested model.",
        style_rules="Transparent and value-focused. Always anchor price with features.",
        required_actions=[]
    ),
    "FINANCING_MIN": PlaybookConfig(
        id="FINANCING_MIN",
        goal="Explain financing options and requirements.",
        style_rules="Clear and structured. Highlight flexibility.",
        required_actions=[]
    ),
    "AVAILABILITY_MIN": PlaybookConfig(
        id="AVAILABILITY_MIN",
        goal="Confirm stock availability or offer alternatives.",
        style_rules="Urgency but honesty. If out of stock, pivot to similar models.",
        required_actions=[]
    ),
    "BOOK_VISIT": PlaybookConfig(
        id="BOOK_VISIT",
        goal="Schedule a showroom visit or test drive.",
        style_rules="Action-oriented. Propose two specific time slots.",
        required_actions=[]
    ),
    "OBJECTION_PRICE": PlaybookConfig(
        id="OBJECTION_PRICE",
        goal="Handle price objection by re-anchoring value or offering financing.",
        style_rules="Empathetic but firm on value. Do not just lower price immediately.",
        required_actions=[]
    ),
    
    # --- DEFAULT ---
    "DEFAULT_ASSIST": PlaybookConfig(
        id="DEFAULT_ASSIST",
        goal="Assist the user with general inquiries.",
        style_rules="Friendly and helpful. Guide towards discovery.",
        required_actions=[]
    ),
}


def get_playbook(key: str) -> Optional[PlaybookConfig]:
    """
    Recupera un playbook por su ID.
    Si no existe, retorna None (el caller debe manejar el fallback).
    """
    return PLAYBOOK_REGISTRY.get(key)
