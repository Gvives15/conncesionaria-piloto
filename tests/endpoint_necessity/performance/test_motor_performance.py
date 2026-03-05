import pytest
from motor_response.api import motor_respond
from motor_response.schemas import MotorRespondIn

@pytest.mark.django_db
def test_motor_respond_benchmark(benchmark, mocker, tenant, contact, tenant_event):
    """Benchmark motor_respond function execution time without network latency."""
    
    # Mock LLM to return immediately
    mocker.patch("motor_response.api.classify_with_openai", return_value={
            "decision": {"primary_event": "BENCHMARK_EVENT", "secondary_events": []},
            "policy": {"response_mode": "FREEFORM"},
            "next_actions": []
        })
    
    payload = MotorRespondIn(
        tenant_id=tenant.tenant_key,
        contact_key=contact.contact_key,
        wa_id=contact.wa_id,
        phone_number_id="1001",
        turn_wamid="wamid.bench",
        text="Benchmark message",
        timestamp_in="2023-01-01T00:00:00Z",
        channel="whatsapp"
    )
    
    def run_motor():
        motor_respond(None, payload)
        
    # Run benchmark
    benchmark(run_motor)
