import pytest
from motor_response.api import motor_respond
from motor_response.schemas import MotorRespondIn

@pytest.mark.django_db
class TestMotorSecurity:
    
    def test_sql_injection_attempt(self, mocker, tenant, contact, tenant_event):
        """Test payload with SQL injection characters."""
        malicious_input = "'; DROP TABLE users; --"
        
        # LLM should see this as just text
        mocker.patch("motor_response.api.classify_with_openai", return_value={
            "decision": {"primary_event": "MALICIOUS_ATTEMPT"},
            "policy": {"response_mode": "FREEFORM"},
            "next_actions": []
        })
        
        payload = MotorRespondIn(
            tenant_id=tenant.tenant_key,
            contact_key=contact.contact_key,
            wa_id=contact.wa_id,
            phone_number_id="1001",
            turn_wamid="wamid.sql",
            text=malicious_input,
            timestamp_in="2023-01-01T00:00:00Z",
            channel="whatsapp"
        )
        
        response = motor_respond(None, payload)
        assert response["ok"] is True
        assert response["turn"]["text_in"] == malicious_input
        # If DB crashed or data was lost, this test would fail or raise exception
        
    def test_xss_attempt(self, mocker, tenant, contact, tenant_event):
        """Test payload with script tags."""
        malicious_input = "<script>alert('XSS')</script>"
        
        mocker.patch("motor_response.api.classify_with_openai", return_value={
            "decision": {"primary_event": "MALICIOUS_ATTEMPT"},
            "policy": {"response_mode": "FREEFORM"},
            "next_actions": []
        })
        
        payload = MotorRespondIn(
            tenant_id=tenant.tenant_key,
            contact_key=contact.contact_key,
            wa_id=contact.wa_id,
            phone_number_id="1001",
            turn_wamid="wamid.xss",
            text=malicious_input,
            timestamp_in="2023-01-01T00:00:00Z",
            channel="whatsapp"
        )
        
        response = motor_respond(None, payload)
        assert response["ok"] is True
        assert "<script>" in response["turn"]["text_in"]
        # The system stores it as text, it should not execute anything server side
