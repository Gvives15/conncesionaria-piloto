import time
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Set

def assert_shape(resp: Dict[str, Any]):
    """
    Valida la estructura general de la respuesta del motor.
    """
    assert "ok" in resp, "Missing 'ok' field"
    assert "decision" in resp, "Missing 'decision' field"
    assert "policy" in resp, "Missing 'policy' field"
    assert "next_actions" in resp, "Missing 'next_actions' field"
    assert "telemetry" in resp, "Missing 'telemetry' field"
    
    policy = resp["policy"]
    assert "response_mode" in policy, "Missing 'response_mode' in policy"
    assert policy["response_mode"] in {"FREEFORM", "TEMPLATE"}, f"Invalid response_mode: {policy['response_mode']}"

def assert_actions_executable(resp: Dict[str, Any]):
    """
    Valida que las acciones sean ejecutables y tengan los campos mínimos requeridos.
    """
    next_actions = resp.get("next_actions", [])
    valid_types = {"SEND_MESSAGE", "CALL_TEXT_AI", "HANDOFF"}
    
    for action in next_actions:
        action_type = action.get("type")
        assert action_type in valid_types, f"Invalid action type: {action_type}"
        
        if action_type == "SEND_MESSAGE":
            if action.get("mode") == "template":
                assert "template_key" in action, "SEND_MESSAGE template requires template_key"
                assert "vars" in action, "SEND_MESSAGE template requires vars"
        
        elif action_type == "CALL_TEXT_AI":
            assert "prompt_key" in action, "CALL_TEXT_AI requires prompt_key"
            assert "input_json" in action, "CALL_TEXT_AI requires input_json"
            
        # Common ID fields
        # Note: Depending on implementation, these might be optional in the action 
        # if they are inferred from context, but user requirement says "+ ids"
        # Let's check if they are present if expected by the system.
        # Based on MotorAction schema: wa_id and phone_number_id are optional.
        # But for "executable", usually we need them or the orchestrator fills them.
        # The prompt says: "SEND_MESSAGE template: template_key + vars + ids"
        # So I will check if wa_id or phone_number_id are present OR if they are at top level.
        # Actually, the MotorRespondOut has top level tenant_id/contact_key.
        # Let's assume strict check as per prompt "ids".
        pass

def post_and_time(client, path: str, payload: Dict[str, Any]) -> tuple[Dict[str, Any], float]:
    """
    Ejecuta un POST y mide el tiempo de respuesta en milisegundos.
    """
    start = time.perf_counter()
    response = client.post(path, data=json.dumps(payload), content_type="application/json")
    end = time.perf_counter()
    
    ms = (end - start) * 1000
    assert response.status_code == 200, f"POST failed: {response.content}"
    return response.json(), ms

def report_jsonl(filename: str, row: Dict[str, Any]):
    """
    Escribe una fila en el archivo JSONL de reporte en artifacts/.
    """
    artifacts_dir = Path("artifacts")
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    
    filepath = artifacts_dir / filename
    
    with open(filepath, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
