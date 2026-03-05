import pytest
import uuid
from .helpers import assert_shape, post_and_time, report_jsonl
from whatsapp_inbound.models import MemoryRecord

@pytest.mark.llm_live
@pytest.mark.django_db
def test_dedupe_live(api_client, tenant, contact, catalog_distribuidora_mvp, templates, memory_open, base_payload):
    """
    Test de deduplicación de eventos.
    Manda el mismo payload dos veces y verifica que no se procese dos veces.
    """
    # 1. Preparar payload con un wamid específico
    wamid = f"wamid.{uuid.uuid4()}"
    payload = base_payload(text="hola precio", turn_wamid=wamid)
    
    # 2. Leer memoria antes
    mem_before = MemoryRecord.objects.get(tenant=tenant, contact=contact)
    len_recent_before = len(mem_before.recent_events or [])
    
    # 3. Primer envío
    resp1, ms1 = post_and_time(api_client, "/v1/motor/respond", payload)
    assert_shape(resp1)
    
    # Validar que el primero procesó OK
    # (Suponiendo que "precio" activa CONSULTA_PRECIO)
    assert resp1["ok"] is True
    
    # Leer memoria intermedia
    mem_mid = MemoryRecord.objects.get(tenant=tenant, contact=contact)
    len_recent_mid = len(mem_mid.recent_events or [])
    # Debería haber crecido en 1
    assert len_recent_mid == len_recent_before + 1, "First request should add to memory"
    
    # 4. Segundo envío (mismo wamid)
    resp2, ms2 = post_and_time(api_client, "/v1/motor/respond", payload)
    
    # 5. Validar comportamiento dedupe
    telemetry = resp2.get("telemetry", {})
    next_actions = resp2.get("next_actions", [])
    
    is_duplicate = telemetry.get("duplicate_turn") is True
    is_empty_actions = len(next_actions) == 0
    # O la respuesta es idéntica a la primera (cache hit total)
    # Pero el caché podría no devolver exactamente el mismo objeto si se serializa diferente, 
    # aunque en este caso debería ser idéntico.
    
    # Condición de éxito: O es marcado como duplicado, o no tiene acciones, o es idéntico al primero (cache)
    # Si es idéntico al primero, telemetry NO tendría duplicate_turn necesariamente, 
    # pero si el sistema detecta duplicado ANTES de procesar, debería devolver lo cacheado.
    
    # Verificamos memoria final
    mem_after = MemoryRecord.objects.get(tenant=tenant, contact=contact)
    len_recent_after = len(mem_after.recent_events or [])
    
    # La memoria NO debe crecer en el segundo intento
    assert len_recent_after == len_recent_mid, "Second request should NOT add to memory"
    
    # Reportar
    report_jsonl("motor_live_results.jsonl", {
        "test": "test_dedupe_live",
        "id": "dedupe_01",
        "payload": payload,
        "first_ms": ms1,
        "second_ms": ms2,
        "is_duplicate_flag": is_duplicate,
        "actions_len_2": len(next_actions),
        "memory_growth": len_recent_after - len_recent_before
    })
