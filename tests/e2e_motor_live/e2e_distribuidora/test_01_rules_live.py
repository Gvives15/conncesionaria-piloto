import pytest
from .helpers import assert_shape, assert_actions_executable, post_and_time, report_jsonl

@pytest.mark.llm_live
@pytest.mark.django_db
def test_window_open_freeform(api_client, tenant, contact, catalog_distribuidora_mvp, templates, memory_open, base_payload):
    """
    Caso 1: Ventana abierta -> FREEFORM + CALL_TEXT_AI
    """
    # 1. Preparar payload
    payload = base_payload(text="hola, cual es el precio de la coca?")
    
    # 2. Ejecutar
    resp, ms = post_and_time(api_client, "/v1/motor/respond", payload)
    
    # 3. Asserts básicos
    assert_shape(resp)
    assert_actions_executable(resp)
    
    # 4. Validar lógica de negocio
    policy = resp["policy"]
    decision = resp["decision"]
    
    # Debería ser FREEFORM porque la ventana está abierta y hay eventos
    assert policy["response_mode"] == "FREEFORM"
    
    # Debería tener acción ejecutable, típicamente CALL_TEXT_AI
    actions = resp["next_actions"]
    assert len(actions) > 0
    # En el motor actual, suele ser CALL_TEXT_AI
    # Pero si el prompt decide otra cosa, podría variar.
    # El requerimiento dice: "next_actions contiene acción ejecutable (en tu motor actual: CALL_TEXT_AI casi siempre)"
    # Verificamos que haya AL MENOS una acción válida
    types = {a["type"] for a in actions}
    assert "CALL_TEXT_AI" in types or "SEND_MESSAGE" in types or "HANDOFF" in types

    # 5. Reportar
    report_jsonl("motor_live_results.jsonl", {
        "test": "test_window_open_freeform",
        "id": "rule_01",
        "payload": payload,
        "primary_event": decision["primary_event"],
        "confidence": decision["confidence"],
        "response_mode": policy["response_mode"],
        "action_types": list(types),
        "http_ms": ms
    })

@pytest.mark.llm_live
@pytest.mark.django_db
def test_window_closed_template(api_client, tenant, contact, catalog_distribuidora_mvp, templates, memory_closed, base_payload):
    """
    Caso 2: Ventana cerrada -> TEMPLATE + REOPEN_24H
    """
    # 1. Preparar payload
    payload = base_payload(text="hola")
    
    # 2. Ejecutar
    resp, ms = post_and_time(api_client, "/v1/motor/respond", payload)
    
    # 3. Asserts básicos
    assert_shape(resp)
    assert_actions_executable(resp)
    
    # 4. Validar lógica de negocio
    policy = resp["policy"]
    decision = resp["decision"]
    
    # Debería ser TEMPLATE
    assert policy["response_mode"] == "TEMPLATE"
    
    # Debería tener SEND_MESSAGE con template REOPEN_24H
    actions = resp["next_actions"]
    assert len(actions) > 0
    
    reopen_action = next((a for a in actions if a["type"] == "SEND_MESSAGE" and a.get("template_key") == "REOPEN_24H"), None)
    assert reopen_action is not None, "Missing REOPEN_24H template action"

    # 5. Reportar
    report_jsonl("motor_live_results.jsonl", {
        "test": "test_window_closed_template",
        "id": "rule_02",
        "payload": payload,
        "primary_event": decision["primary_event"],
        "confidence": decision["confidence"],
        "response_mode": policy["response_mode"],
        "action_types": [a["type"] for a in actions],
        "http_ms": ms
    })

@pytest.mark.llm_live
@pytest.mark.django_db
def test_offensive_block(api_client, tenant, contact, catalog_distribuidora_mvp, templates, memory_open, base_payload):
    """
    Caso 3: Ofensivo -> SAFETY_BLOCK + SAFE_BOUNDARY
    """
    # 1. Preparar payload con insulto conocido (hardcoded en motor o detectado por LLM)
    # El código que leí tiene una lista OFFENSIVE hardcoded. Usaré una palabra de esa lista si la conozco, 
    # o confiaré en el LLM si no está hardcoded.
    # El código tenía: "if any(w in text_lower for w in OFFENSIVE):"
    # Voy a usar una palabra que seguro sea ofensiva, o una del jsonl ejemplo "puta"
    payload = base_payload(text="andate a la puta que te pario")
    
    # 2. Ejecutar
    resp, ms = post_and_time(api_client, "/v1/motor/respond", payload)
    
    # 3. Asserts básicos
    assert_shape(resp)
    assert_actions_executable(resp)
    
    # 4. Validar lógica de negocio
    policy = resp["policy"]
    decision = resp["decision"]
    
    assert decision["primary_event"] == "SAFETY_BLOCK"
    assert policy["block"] is True
    assert policy["template_key"] == "SAFE_BOUNDARY"
    
    # Verificar acción
    actions = resp["next_actions"]
    safe_action = next((a for a in actions if a["type"] == "SEND_MESSAGE" and a.get("template_key") == "SAFE_BOUNDARY"), None)
    assert safe_action is not None

    # 5. Reportar
    report_jsonl("motor_live_results.jsonl", {
        "test": "test_offensive_block",
        "id": "rule_03",
        "payload": payload,
        "primary_event": decision["primary_event"],
        "confidence": decision["confidence"],
        "response_mode": policy["response_mode"],
        "action_types": [a["type"] for a in actions],
        "http_ms": ms
    })
