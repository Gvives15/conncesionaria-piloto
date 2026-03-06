from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

# OpenAI SDK (nuevo)
# pip install openai
from openai import OpenAI


def _client() -> OpenAI:
    return OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def classify_with_openai(
    *,
    model: str,  # Kept for compatibility but might be unused if Stored Prompt dictates model
    user_input_json: Dict[str, Any],
    timeout_s: int = 20,
) -> Dict[str, Any]:
    """
    Devuelve un dict ya parseado desde el JSON que retorna el modelo.
    Requisito: el modelo DEBE devolver JSON puro (sin markdown).
    MODO ÚNICO: Stored Prompt en OpenAI (Responses API).
    """
    c = _client()

    # Usamos Responses API (Stored Prompt)
    # ID del prompt dinámico desde variable de entorno
    prompt_id = os.getenv("LLM_CLASSIFIER_PROMPT_ID")
    
    if not prompt_id:
        return {
            "ok": False,
            "error": "MISSING_ENV_VAR: LLM_CLASSIFIER_PROMPT_ID",
            "raw": ""
        }
    
    # Preparamos el payload completo como un JSON string para pasarlo como variable única
    full_context_json = json.dumps(user_input_json, ensure_ascii=False)
    
    # DEBUG: Imprimir el input que se va a enviar
    print(f"\n--- DEBUG LLM INPUT ---\n{full_context_json}\n--- END DEBUG ---")

    try:
        resp = c.responses.create(
            prompt={
                "id": prompt_id,
                "variables": {
                    "input_json": full_context_json
                }
            },
            # Mensaje de refuerzo por si el prompt en plataforma no lo tiene
            input=[
                {
                    "role": "user",
                    "content": f"INPUT_JSON: {full_context_json}"
                }
            ],
            text={
                "format": {
                    "type": "text"
                }
            },
            max_output_tokens=2048,
        )

        # Extraer texto final
        out_text = ""
        if resp.output and resp.output[0].content:
            # Asumiendo que el contenido es texto
            out_text = resp.output[0].content[0].text or ""

    except Exception as e:
        # En caso de error, devolvemos estructura de error para que no rompa el flujo
        return {
            "ok": False,
            "error": f"LLM_API_ERROR: {str(e)}",
            "raw": ""
        }
    
    out_text = out_text.strip()

    # Parse seguro y normalización de salida
    import time
    start_parse = time.time()
    try:
        parsed_out = json.loads(out_text)
        
        # Telemetría básica de parseo
        telemetry_extra = {
            "parse_time_ms": int((time.time() - start_parse) * 1000),
            "raw_length": len(out_text),
            "model_used": model
        }
        
        # Estructura base esperada para evitar errores en api.py
        normalized_out = {
            "ok": True,
            "decision": {
                "primary_event": parsed_out.get("decision", {}).get("primary_event", "FALLBACK"),
                "secondary_events": parsed_out.get("decision", {}).get("secondary_events", []),
                "confidence": parsed_out.get("decision", {}).get("confidence", 0.0),
            },
            "policy": {
                "response_mode": parsed_out.get("policy", {}).get("response_mode", "FREEFORM"),
                "template_key": parsed_out.get("policy", {}).get("template_key"),
                "handoff": parsed_out.get("policy", {}).get("handoff", False),
                "block": parsed_out.get("policy", {}).get("block", False),
                "block_reason": parsed_out.get("policy", {}).get("block_reason"),
            },
            "next_actions": parsed_out.get("next_actions", []),
            "memory_update": parsed_out.get("memory_update", {}),
            "telemetry": {**parsed_out.get("telemetry", {}), **telemetry_extra},
        }
        return normalized_out

    except Exception as e:
        # si devuelve basura, devolvemos estructura mínima de error
        return {
            "ok": False,
            "error": "LLM_NON_JSON",
            "raw": out_text[:2000],
            "telemetry": {"parse_error": str(e), "model_used": model}
        }


def extract_signals(
    *,
    user_input_json: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Función específica para el EXTRACTOR (Ojos).
    Utiliza un prompt INLINE para extraer señales sin decidir estrategia.
    """
    c = _client()
    
    # Modelo configurable desde env, default gpt-4o-mini para velocidad/costo
    model = os.getenv("LLM_EXTRACTOR_MODEL", "gpt-4o")

    # Prompt del sistema inline (Ojos puros)
    system_prompt = """
You are a SIGNAL EXTRACTOR for a sales bot.
Your ONLY job is to read the user input and extract structured data.
You DO NOT decide strategy. You DO NOT write replies. You DO NOT take actions.

OUTPUT JSON FORMAT:
{
  "intent": "string", // One of: ASK_PRICE, ASK_FINANCING, ASK_AVAILABILITY, BOOK_TEST_DRIVE, SCHEDULE_VISIT, HANDOFF_REQUEST, COMPLAINT, GREETING, OTHER
  "objection_primary": "string|null", // E.g.: PRICE_TOO_HIGH, NO_STOCK, BAD_REVIEW, TIMING, COMPETITOR
  "risk_flag": boolean, // true if user is aggressive, insulting, or threatening
  "entities": {
    "vehicle": {
      "make": "string|null",
      "model": "string|null",
      "trim": "string|null",
      "year": "string|null",
      "new_or_used": "string|null"
    },
    "commercial": {
      "budget": "string|null",
      "payment_type": "string|null", // cash, finance, lease
      "timeframe": "string|null",
      "city": "string|null"
    }
  }
}

RULES:
1. Extract what is EXPLICITLY stated or strongly implied.
2. If info is missing, use null. Do not guess.
3. "intent" must be the PRIMARY user intention.
4. "objection_primary" is the main blocker if any.
5. "risk_flag" is strict: insults, racism, threats = true.
    """.strip()

    user_text = json.dumps(user_input_json, ensure_ascii=False)

    try:
        resp = c.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"INPUT: {user_text}"}
            ],
            response_format={"type": "json_object"},
            temperature=0.0, # Determinístico
            max_tokens=512
        )
        
        out_text = resp.choices[0].message.content or "{}"
        parsed = json.loads(out_text)
        
        # Mapeo de seguridad para cumplir contrato interno Signals
        return {
            "intent": parsed.get("intent", "OTHER"),
            "objection": parsed.get("objection_primary"), # Mapeo objection_primary -> objection
            "risk": parsed.get("risk_flag", False),
            "entities": parsed.get("entities", {})
        }

    except Exception as e:
        # Fallback seguro en caso de error de API o parseo
        print(f"EXTRACTOR ERROR: {e}")
        return {
            "intent": "GENERAL",
            "objection": None,
            "risk": False,
            "entities": {}
        }


def build_classifier_input(
    *,
    tenant_id: str,
    domain: str,
    turn_wamid: str,
    text_in: Optional[str],
    timestamp_in: Optional[str],
    channel: str,
    wa_id: str,
    phone_number_id: str,
    window_open: bool,
    last_user_message_at: Optional[str],
    memory: Dict[str, Any],
    tenant_events: List[Dict[str, Any]],
    templates: List[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return {
        "tenant": {"tenant_id": tenant_id, "domain": domain},
        "turn": {
            "turn_wamid": turn_wamid,
            "text_in": text_in,
            "timestamp_in": timestamp_in,
            "channel": channel,
            "wa_id": wa_id,
            "phone_number_id": phone_number_id,
        },
        "window": {"window_open": window_open, "last_user_message_at": last_user_message_at},
        "memory": memory,
        "catalog": {
            "events": tenant_events,
            "templates": templates or [],
        },
        "instructions": (
            "Window is CLOSED (>24h). You MUST reply with a TEMPLATE from catalog.templates."
            if not window_open
            else "Window is OPEN. You can use freeform text or templates."
        ),
    }
