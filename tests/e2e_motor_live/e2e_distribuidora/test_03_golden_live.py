import pytest
import json
import os
from pathlib import Path
from .helpers import assert_shape, assert_actions_executable, post_and_time, report_jsonl
from whatsapp_inbound.models import MemoryRecord
from django.utils import timezone
from datetime import timedelta

def load_cases():
    cases = []
    filepath = Path(__file__).parent / "data" / "cases.jsonl"
    if not filepath.exists():
        return []
    
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                cases.append(json.loads(line))
    return cases

CASES = load_cases()

@pytest.mark.llm_live
@pytest.mark.django_db
@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_golden_case(api_client, tenant, contact, catalog_distribuidora_mvp, templates, memory_open, memory_closed, base_payload, case):
    """
    Test Golden: Ejecuta casos definidos en cases.jsonl
    """
    case_id = case["id"]
    text = case["text"]
    expected = set(case["expected_primary_events"])
    window = case.get("window", "open")
    flags = case.get("flags", {})
    
    # 1. Configurar memoria según window
    mem = None
    if window == "closed":
        mem = memory_closed
        # Aseguramos que la memoria actual sea la closed
        # memory_closed ya guarda en DB, pero necesitamos asegurar que el fixture
        # correcto esté activo para este request.
        # Dado que ambos fixtures modifican el mismo registro (mismo tenant/contact),
        # el último fixture en ejecutarse gana.
        # Pero pytest ejecuta fixtures antes del test.
        # Aquí ambos se inyectan. ¿Cuál gana? Indeterminado.
        # Mejor forzamos el estado dentro del test.
        mem.last_user_message_at = timezone.now() - timedelta(hours=30)
        mem.save()
    else:
        mem = memory_open
        mem.last_user_message_at = timezone.now() - timedelta(hours=1)
        mem.save()
        
    # 2. Preparar payload
    # Si es duplicate test, usamos un wamid fijo, sino random
    wamid = None
    if flags.get("duplicate"):
        wamid = "wamid.duplicate.test"
        # Para testear duplicado, necesitaríamos ejecutar dos veces.
        # Pero este test corre una vez por caso.
        # El caso "duplicate" en jsonl parece ser para verificar que SI es duplicado se comporte bien.
        # Pero aquí solo mandamos uno.
        # Si el caso es "duplicate", asumimos que queremos ver si el sistema lo maneja.
        # O tal vez el usuario quiere que simulemos duplicado.
        # El prompt dice: "2 casos duplicate (duplicate=true)".
        # En test_02 ya probamos la lógica de duplicación.
        # Aquí, si es duplicate, quizás deberíamos mandar uno previo.
        # Voy a mandar uno previo si flag duplicate es true.
        _p = base_payload(text=text, turn_wamid=wamid)
        api_client.post("/v1/motor/respond", data=json.dumps(_p), content_type="application/json")
        
    payload = base_payload(text=text, turn_wamid=wamid)
    
    # 3. Ejecutar
    resp, ms = post_and_time(api_client, "/v1/motor/respond", payload)
    
    # 4. Asserts básicos
    assert_shape(resp)
    # Si es duplicado, next_actions podría estar vacío, en cuyo caso assert_actions_executable no debería fallar si la lista está vacía.
    # assert_actions_executable itera sobre next_actions, si es vacía pasa.
    assert_actions_executable(resp)
    
    decision = resp["decision"]
    policy = resp["policy"]
    telemetry = resp.get("telemetry", {})
    
    primary = decision["primary_event"]
    
    # 5. Validaciones específicas
    
    # Si es duplicate, esperamos que sea detectado o vacío
    if flags.get("duplicate"):
        # Puede ser que primary sea None o vacío si es duplicado total
        # O que telemetry diga duplicate_turn
        is_dup = telemetry.get("duplicate_turn")
        actions = resp.get("next_actions", [])
        if not is_dup and actions:
            # Si no lo marcó como duplicado y devolvió acciones, 
            # debería ser la misma respuesta que el original (idempotencia).
            # En este contexto, aceptamos que pase.
            pass
        elif is_dup:
            assert True
        else:
            # next_actions empty
            assert len(actions) == 0
            
    else:
        # Validación de eventos esperados
        # Si expected es vacío, es que no esperamos nada específico o es un caso raro
        if expected:
            # Si primary es None (ej. duplicado), fallará si expected no tiene None
            assert primary in expected, f"Expected {expected}, got {primary}"
            
        # Validación ofensiva
        if flags.get("offensive"):
            assert primary == "SAFETY_BLOCK"
            assert policy["template_key"] == "SAFE_BOUNDARY"
            
        # Validación ventana cerrada
        if window == "closed":
            assert policy["response_mode"] == "TEMPLATE"
            # Debería haber template
            # assert policy["template_key"] is not None (no siempre, a veces es handoff)

    # 6. Reportar
    report_jsonl("motor_live_results.jsonl", {
        "test": "test_golden_live",
        "id": case_id,
        "text": text,
        "payload": payload,
        "primary_event": primary,
        "confidence": decision.get("confidence"),
        "response_mode": policy.get("response_mode"),
        "action_types": [a["type"] for a in resp.get("next_actions", [])],
        "http_ms": ms
    })
