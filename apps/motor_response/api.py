from __future__ import annotations

import os
import os
import logging
import time
from datetime import timedelta
from typing import Any, Dict, List, Optional

from django.core.cache import cache
from django.db import transaction
from django.utils import timezone
from ninja import Router

from whatsapp_inbound.models import (
    Tenant,
    Contact,
    MemoryRecord,
    TenantEvent,
    Template,
)

from .schemas import MotorRespondIn, MotorRespondOut
from .llm_classifier import build_classifier_input, classify_with_openai


logger = logging.getLogger(__name__)
router = Router()

OFFENSIVE = ["puta", "mierda", "idiota", "estafa"]


def _get_or_create_tenant(tenant_id: str) -> Tenant:
    t = Tenant.objects.filter(tenant_key=tenant_id).first()
    if t:
        return t
    t = Tenant.objects.filter(name=tenant_id).first()
    if t:
        if not t.tenant_key:
            t.tenant_key = tenant_id
            if not t.business_name:
                t.business_name = t.name or tenant_id
            t.save(update_fields=["tenant_key", "business_name"])
        return t
    tenant, _ = Tenant.objects.get_or_create(
        tenant_key=tenant_id,
        defaults={"business_name": tenant_id, "name": tenant_id},
    )
    return tenant


def _iso(dt) -> Optional[str]:
    if not dt:
        return None
    try:
        return dt.isoformat()
    except Exception:
        return None


def _load_tenant_events(tenant: Tenant) -> List[Dict[str, Any]]:
    cache_key = f"tenant:{tenant.tenant_key}:events:v1"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    qs = TenantEvent.objects.filter(tenant=tenant, is_active=True).order_by("name")
    out = []
    for ev in qs:
        out.append(
            {
                "name": ev.name,
                "max_points": ev.max_points,
                "triggers": ev.triggers or [],
                "template_key": ev.template_key or "",
                "is_active": ev.is_active,
            }
        )
    cache.set(cache_key, out, timeout=300)
    return out


def _load_available_templates(tenant: Tenant) -> List[Dict[str, Any]]:
    cache_key = f"tenant:{tenant.tenant_key}:templates:v1"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    qs = Template.objects.filter(tenant=tenant, active=True).order_by("name")
    out = []
    for t in qs:
        out.append({
            "name": t.name,
            "category": t.category,
            "language": t.language,
            "components": t.components_json
        })
    cache.set(cache_key, out, timeout=300)
    return out


def _default_actions_call_text_ai(payload: MotorRespondIn, primary_event: str, secondary_events: List[str], confidence: float):
    return [
        {
            "type": "CALL_TEXT_AI",
            "channel": payload.channel,
            "prompt_key": "GEN_REPLY_V1",
            "input_json": {
                "tenant_id": payload.tenant_id,
                "contact_key": payload.contact_key,
                "wa_id": payload.wa_id,
                "phone_number_id": payload.phone_number_id,
                "turn_wamid": payload.turn_wamid,
                "text_in": payload.text,
                "primary_event": primary_event,
                "secondary_events": secondary_events,
                "confidence": confidence,
            },
            "wa_id": payload.wa_id,
            "phone_number_id": payload.phone_number_id,
        }
    ]


@router.post("/v1/motor/respond", response=MotorRespondOut)
def motor_respond(request, payload: MotorRespondIn):
    # Lógica de Deduplicación e Idempotencia
    dedup_key = None
    lock_key = None
    
    # 0. Validar WAMID para dedup
    if payload.turn_wamid and payload.turn_wamid.strip():
        dedup_key = f"motor:response:{payload.tenant_id}:{payload.turn_wamid}"
        lock_key = f"motor:processing:{payload.tenant_id}:{payload.turn_wamid}"
        
        # 1. Check respuesta existente (Idempotencia)
        cached_response = cache.get(dedup_key)
        if cached_response:
            logger.info(f"[DEDUP] Returning cached response for {payload.turn_wamid}")
            return cached_response

        # 2. Check Lock (Concurrencia)
        # Simple spin-lock de hasta 5 segundos
        attempts = 0
        while cache.get(lock_key) and attempts < 10:
             time.sleep(0.5)
             attempts += 1
             cached_response_after_wait = cache.get(dedup_key)
             if cached_response_after_wait:
                 logger.info(f"[DEDUP] Returning cached response after wait for {payload.turn_wamid}")
                 return cached_response_after_wait
        
        # Si sigue bloqueado después de 5s, asumimos que el proceso anterior murió o está muy lento.
        # Opción: Fallar o continuar. Para robustez, continuamos pero logueamos warning.
        if attempts >= 10:
            logger.warning(f"[DEDUP] Lock timeout for {payload.turn_wamid}, proceeding anyway")

        # 3. Set Lock (1 min expiration)
        cache.set(lock_key, "PROCESSING", timeout=60)

    try:
        # Ejecutar lógica real
        response_data = _motor_respond_impl(payload)
        
        # 4. Guardar respuesta (24h TTL)
        if dedup_key:
             cache.set(dedup_key, response_data, timeout=86400)
        
        return response_data
    except Exception as e:
        logger.error(f"Error processing motor logic: {e}")
        raise e
    finally:
        # 5. Liberar Lock
        if lock_key:
            cache.delete(lock_key)


def _motor_respond_impl(payload: MotorRespondIn):
    tenant = _get_or_create_tenant(payload.tenant_id)

    # contact + memory (si no existe, no lo creamos acá; inbound ya lo crea)
    contact = Contact.objects.filter(tenant=tenant, contact_key=payload.contact_key).first()
    mem = None
    last_user_message_at = None
    if contact:
        mem = MemoryRecord.objects.filter(tenant=tenant, contact=contact).first()
        if mem:
            last_user_message_at = mem.last_user_message_at

    now = timezone.now()
    text_lower = (payload.text or "").lower()

    # 1) Ventana 24h (check only)
    window_open = True
    if last_user_message_at:
        window_open = (now - last_user_message_at) <= timedelta(hours=24)

    # 2) Bloqueo por lenguaje inapropiado (Prioridad 1, incluso si ventana cerrada)
    if any(w in text_lower for w in OFFENSIVE):
        out = {
            "ok": True,
            "tenant_id": tenant.tenant_key or payload.tenant_id,
            "contact_key": payload.contact_key,
            "turn": {"turn_wamid": payload.turn_wamid, "text_in": payload.text},
            "decision": {"primary_event": "SAFETY_BLOCK", "secondary_events": [], "confidence": 1.0},
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
                    "channel": payload.channel,
                    "mode": "template",
                    "template_key": "SAFE_BOUNDARY",
                    "vars": {},
                    "wa_id": payload.wa_id,
                    "phone_number_id": payload.phone_number_id,
                }
            ],
            "memory_update": None,
            "telemetry": {"window_open": window_open},
        }
        return out

    # 3) Catálogo de eventos y templates del tenant
    tenant_events = _load_tenant_events(tenant)
    available_templates = _load_available_templates(tenant)

    # Si no hay eventos, definimos fallback pero continuamos para intentar usar templates si ventana cerrada
    if not tenant_events and window_open:
        # Lógica original de fallback si no hay eventos Y ventana abierta
        # (Si ventana cerrada, queremos que pase al LLM para elegir template aunque no haya eventos)
        primary_event = "FALLBACK"
        secondary_events = []
        confidence = 0.1
 
        if contact:
            with transaction.atomic():
                mem_obj, _ = MemoryRecord.objects.get_or_create(tenant=tenant, contact=contact)
                mem_obj.active_primary_event = primary_event
                mem_obj.active_secondary_events = secondary_events
                recent = mem_obj.recent_events or []
                recent.append({"ts": _iso(now), "event": primary_event, "confidence": confidence})
                mem_obj.recent_events = recent[-20:]
                mem_obj.updated_at = timezone.now()
                mem_obj.save(update_fields=["active_primary_event", "active_secondary_events", "recent_events", "updated_at"])

        return {
            "ok": True,
            "tenant_id": tenant.tenant_key or payload.tenant_id,
            "contact_key": payload.contact_key,
            "turn": {"turn_wamid": payload.turn_wamid, "text_in": payload.text},
            "decision": {"primary_event": primary_event, "secondary_events": secondary_events, "confidence": confidence},
            "policy": {"response_mode": "FREEFORM", "template_key": None, "handoff": False, "block": False, "block_reason": None},
            "next_actions": _default_actions_call_text_ai(payload, primary_event, secondary_events, confidence),
            "memory_update": {
                "active_primary_event": primary_event,
                "active_secondary_events": secondary_events,
                "recent_events": [{"ts": _iso(now), "event": primary_event, "confidence": confidence}],
                "scores_json": {},
            },
            "telemetry": {"window_open": True, "llm_used": False, "reason": "NO_EVENTS_SEEDED"},
        }

    # --- IMPORTACIONES DEL NUEVO PIPELINE HÍBRIDO ---
    from .llm_classifier import extract_signals
    from .schemas import Signals, SalesState, PlaybookConfig, RouterDecision
    from .router import decide_playbook
    from .playbooks import get_playbook
    from .state_manager import update_sales_state
    from .action_builder import build_actions_from_playbook

    # 1. Extractor (Ojos)
    signals_data = extract_signals(user_input_json={"text": payload.text})
    signals = Signals(**signals_data)

    # 2. Sales State (Memoria)
    # Inicializar o recuperar estado
    state_data = mem.sales_state_json if mem else {}
    current_state = SalesState(**state_data)
    
    # Actualizar estado con señales nuevas
    sales_state = update_sales_state(current_state, signals)
    
    # PERSISTENCIA (Opcional en esta fase, pero útil para debugging)
    # Por ahora solo actualizamos en memoria para el router, 
    # la persistencia real a DB se puede hacer aquí o al final.
    # Para cumplir "Sales State deje de estar dormido", lo persistimos.
    if contact and mem:
        mem.sales_state_json = sales_state.model_dump()
        # No guardamos todavía para no hacer doble write, 
        # pero el objeto 'mem' ya tiene el dato fresco.
        # Si quisiéramos guardar YA: mem.save(update_fields=["sales_state_json", "updated_at"])
    
    # 3. Router (Cerebro)
    router_decision = decide_playbook(signals, sales_state, window_open)
    
    # 4. Playbook (Estrategia)
    playbook = get_playbook(router_decision.playbook_key)
    
    # 5. Action Gen (Boca) - Shadow Mode
    # Generamos las acciones pero no las devolvemos todavía
    shadow_actions = build_actions_from_playbook(
        payload=payload,
        playbook=playbook,
        state=sales_state,
        signals=signals
    )
    
    # Logueamos la decisión completa para validación
    logger.info(f"[HYBRID MOTOR] Decision: {router_decision.playbook_key} | Actions: {len(shadow_actions)} generated")
    # Para debug profundo: logger.debug(f"[HYBRID ACTIONS]: {shadow_actions}")

    # --- FIN PIPELINE HÍBRIDO (CONTINÚA FLUJO LEGACY) ---

    # 4) Construir input para la IA clasificadora
    memory_json = {
        "active_primary_event": (mem.active_primary_event if mem else None),
        "active_secondary_events_json": (mem.active_secondary_events if mem else []),
        "recent_events_json": (mem.recent_events if mem else []),
        "summary": (mem.summary if mem else ""),
        "facts_json": (mem.facts_json if mem else []),
    }

    classifier_input = build_classifier_input(
        tenant_id=tenant.tenant_key or payload.tenant_id,
        domain=tenant.domain or "generic",
        turn_wamid=payload.turn_wamid,
        text_in=payload.text,
        timestamp_in=payload.timestamp_in,
        channel=payload.channel,
        wa_id=payload.wa_id,
        phone_number_id=payload.phone_number_id,
        window_open=window_open,
        last_user_message_at=_iso(last_user_message_at),
        memory=memory_json,
        tenant_events=tenant_events,
        templates=available_templates,
    )

    # 5) Llamar al modelo
    model = os.getenv("MOTOR_CLASSIFIER_MODEL", "gpt-4o")
    
    # Usamos Stored Prompt Mode exclusivamente
    llm_out = classify_with_openai(
        model=model,
        user_input_json=classifier_input,
    )

    # 6) Normalizar salida del LLM
    # La salida ya viene parcialmente normalizada desde llm_classifier.py
    # Aquí aplicamos reglas de negocio finales
    
    warning_flag = None

    # Check error del LLM (ok=False)
    if not isinstance(llm_out, dict) or llm_out.get("ok") is False:
        error_msg = llm_out.get("error") if isinstance(llm_out, dict) else "Invalid output format"
        logger.error(f"LLM Error for tenant {tenant.tenant_key}: {error_msg}. Raw: {llm_out.get('raw') if isinstance(llm_out, dict) else llm_out}")
        warning_flag = "LLM_FALLBACK_TRIGGERED"

        primary_event = "FALLBACK"
        secondary_events = []
        confidence = 0.1
        # Default policy
        policy = {"response_mode": "FREEFORM", "template_key": None, "handoff": False, "block": False, "block_reason": None}
        next_actions = []
        
        # Fallback de emergencia si ventana cerrada y LLM falla
        if not window_open:
            policy["response_mode"] = "TEMPLATE"
            policy["template_key"] = "REOPEN_24H"
            next_actions = [{
                "type": "SEND_MESSAGE",
                "channel": payload.channel,
                "mode": "template",
                "template_key": "REOPEN_24H",
                "vars": {},
                "wa_id": payload.wa_id,
                "phone_number_id": payload.phone_number_id,
            }]
        else:
            # Fallback ventana abierta -> Generar texto
            next_actions = _default_actions_call_text_ai(payload, primary_event, secondary_events, confidence)

        memory_update = {
            "active_primary_event": primary_event,
            "active_secondary_events": secondary_events,
            "recent_events": [{"ts": _iso(now), "event": primary_event, "confidence": confidence}],
            "scores_json": {},
            "summary": None,
            "facts_json": []
        }
        telemetry = {"window_open": window_open, "llm_used": True, "llm_error": error_msg, "warning": "llm_fallback", "raw": llm_out.get("raw") if isinstance(llm_out, dict) else str(llm_out)}
    else:
        # Extracción segura gracias a la pre-normalización
        decision = llm_out.get("decision", {})
        policy_data = llm_out.get("policy", {})
        next_actions_raw = llm_out.get("next_actions", [])
        memory_data = llm_out.get("memory_update", {})
        telemetry = llm_out.get("telemetry", {})

        primary_event = decision.get("primary_event")
        secondary_events = decision.get("secondary_events")
        confidence = float(decision.get("confidence") or 0.0)
        
        # Normalizar policy
        policy = {
            "response_mode": str(policy_data.get("response_mode") or "FREEFORM").upper(),
            "template_key": policy_data.get("template_key"),
            "handoff": bool(policy_data.get("handoff")),
            "block": bool(policy_data.get("block")),
            "block_reason": policy_data.get("block_reason")
        }

        # Normalizar next_actions (Estandarización Action/Type)
        next_actions = []
        for ax in next_actions_raw:
            # LLM puede devolver 'action' o 'type'
            ax_type = ax.get("type") or ax.get("action")
            if not ax_type: continue
            
            normalized_ax = ax.copy()
            normalized_ax["type"] = ax_type
            if "action" in normalized_ax: del normalized_ax["action"] # Limpieza
            
            # Inyectar IDs si faltan
            if not normalized_ax.get("wa_id"): normalized_ax["wa_id"] = payload.wa_id
            if not normalized_ax.get("phone_number_id"): normalized_ax["phone_number_id"] = payload.phone_number_id
            
            next_actions.append(normalized_ax)

        # Validación estricta de ventana cerrada
        if not window_open:
            if policy["response_mode"] != "TEMPLATE":
                policy["response_mode"] = "TEMPLATE"
                if not policy["template_key"]:
                     policy["template_key"] = "REOPEN_24H"
            
            # Si no hay acciones de template válidas, forzamos una
            has_template_action = any(a["type"] == "SEND_MESSAGE" and a.get("mode") == "template" for a in next_actions)
            
            if not has_template_action:
                next_actions = [{
                    "type": "SEND_MESSAGE",
                    "channel": payload.channel,
                    "mode": "template",
                    "template_key": policy["template_key"],
                    "vars": {}, 
                    "wa_id": payload.wa_id,
                    "phone_number_id": payload.phone_number_id,
                }]
        else:
            # Regla dura del MVP: si policy FREEFORM => NO texto directo del LLM, acción CALL_TEXT_AI
            if policy["response_mode"] == "FREEFORM":
                # Si el LLM devolvió acciones CALL_TEXT_AI, las usamos. Si no, generamos default.
                has_gen_action = any(a["type"] == "CALL_TEXT_AI" for a in next_actions)
                if not has_gen_action:
                     next_actions = _default_actions_call_text_ai(payload, primary_event, secondary_events, confidence)

            # Si policy TEMPLATE y no hay template_key, ponemos HANDOFF_GENERIC si handoff=true
            if policy["response_mode"] == "TEMPLATE":
                if policy["handoff"] and not policy["template_key"]:
                    policy["template_key"] = "HANDOFF_GENERIC"
        
        memory_update = memory_data
    
    # 7) Persistir MemoryRecord con primary/secondary/recent/scores
    if contact:
        with transaction.atomic():
            mem_obj, _ = MemoryRecord.objects.get_or_create(tenant=tenant, contact=contact)

            mem_obj.active_primary_event = memory_update.get("active_primary_event") or primary_event
            # HOTFIX: Ensure list is never None
            mem_obj.active_secondary_events = (memory_update.get("active_secondary_events") or secondary_events) or []

            # append recent
            recent_append = {"ts": _iso(now), "event": primary_event, "confidence": confidence}
            recent = list(mem_obj.recent_events or [])
            recent.append(recent_append)
            mem_obj.recent_events = recent[-20:]

            # summary (CRÍTICO: Actualizar la memoria narrativa)
            new_summary = memory_update.get("summary")
            if new_summary and isinstance(new_summary, str):
                mem_obj.summary = new_summary

            # facts_json (opcional: si la IA extrajo nuevos datos)
            new_facts = memory_update.get("facts_json")
            if isinstance(new_facts, list):
                # Estrategia simple: reemplazar. 
                # Idealmente podríamos hacer merge, pero por ahora confiamos en el LLM.
                mem_obj.facts_json = new_facts

            # scores_json (opcional)
            scores_json = memory_update.get("scores_json")
            if isinstance(scores_json, dict) and scores_json:
                mem_obj.scores_json = scores_json

            mem_obj.updated_at = timezone.now()
            mem_obj.save(
                update_fields=[
                    "active_primary_event",
                    "active_secondary_events",
                    "recent_events",
                    "summary",
                    "facts_json",
                    "scores_json",
                    "updated_at",
                ]
            )

    # 8) Salida final
    return {
        "ok": True,
        "tenant_id": tenant.tenant_key or payload.tenant_id,
        "contact_key": payload.contact_key,
        "turn": {"turn_wamid": payload.turn_wamid, "text_in": payload.text},
        "decision": {"primary_event": primary_event, "secondary_events": secondary_events, "confidence": round(confidence, 2)},
        "policy": {
            "response_mode": str(policy.get("response_mode") or "FREEFORM").upper(),
            "template_key": policy.get("template_key"),
            "handoff": bool(policy.get("handoff") or False),
            "block": bool(policy.get("block") or False),
            "block_reason": policy.get("block_reason"),
        },
        "next_actions": next_actions,
        "memory_update": {
            "active_primary_event": memory_update.get("active_primary_event") or primary_event,
            "active_secondary_events": memory_update.get("active_secondary_events") or secondary_events,
            "recent_events": [{"ts": _iso(now), "event": primary_event, "confidence": confidence}],
            "scores_json": memory_update.get("scores_json") or {},
            "summary": memory_update.get("summary"),
            "facts_json": memory_update.get("facts_json") or [],
        },
        "telemetry": {"window_open": window_open, **(telemetry or {})},
    }
