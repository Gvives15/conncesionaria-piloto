import pytest
import json
from datetime import timedelta
from django.utils import timezone
from motor_response.api import motor_respond
from motor_response.schemas import MotorRespondIn
from whatsapp_inbound.models import MemoryRecord, OutboxEvent, TenantEvent

@pytest.mark.django_db
class TestMotorFunctional:
    
    def _make_payload(self, tenant, contact, text="Hello"):
        return MotorRespondIn(
            tenant_id=tenant.tenant_key,
            contact_key=contact.contact_key,
            wa_id=contact.wa_id,
            phone_number_id="1001",
            turn_wamid="wamid.test.123",
            text=text,
            timestamp_in=timezone.now().isoformat(),
            channel="whatsapp"
        )

    def test_happy_path(self, mocker, tenant, contact, tenant_event):
        """Test normal flow with open window and valid LLM response."""
        
        # Mock LLM response
        mock_llm = mocker.patch("motor_response.api.classify_with_openai")
        mock_llm.return_value = {
            "decision": {
                "primary_event": "TEST_EVENT",
                "secondary_events": [],
                "confidence": 0.95
            },
            "policy": {
                "response_mode": "FREEFORM",
                "template_key": None
            },
            "next_actions": [
                {"type": "CALL_TEXT_AI", "prompt_key": "GEN_REPLY_V1"}
            ],
            "memory_update": {
                "summary": "Updated summary from LLM",
                "recent_events": [{"event": "TEST_EVENT", "confidence": 0.95}]
            }
        }

        payload = self._make_payload(tenant, contact, "Test message")
        
        # Act
        response = motor_respond(None, payload)
        
        # Assert
        assert response["ok"] is True
        assert response["decision"]["primary_event"] == "TEST_EVENT"
        assert response["policy"]["response_mode"] == "FREEFORM"
        
        # Check Memory Persistence
        mem = MemoryRecord.objects.get(tenant=tenant, contact=contact)
        assert mem.summary == "Updated summary from LLM"
        assert mem.active_primary_event == "TEST_EVENT"

    def test_closed_window(self, mocker, tenant, contact, memory_record, template):
        """Test flow when 24h window is closed."""
        
        # Set last message to > 24h ago
        memory_record.last_user_message_at = timezone.now() - timedelta(hours=25)
        memory_record.save()
        
        # Mock LLM response (even if LLM says FREEFORM, system should force TEMPLATE)
        mock_llm = mocker.patch("motor_response.api.classify_with_openai")
        mock_llm.return_value = {
            "decision": {"primary_event": "GREETING", "confidence": 0.8},
            "policy": {"response_mode": "FREEFORM"},  # LLM tries to be free
            "next_actions": []
        }

        payload = self._make_payload(tenant, contact, "Hello again")
        
        # Act
        response = motor_respond(None, payload)
        
        # Assert
        assert response["telemetry"]["window_open"] is False
        assert response["policy"]["response_mode"] == "TEMPLATE"
        # Should fallback to REOPEN_24H or similar if LLM didn't provide one
        # In the code, if window closed and policy forced to TEMPLATE, it checks for template_key
        # If not provided by LLM, it defaults to REOPEN_24H
        assert response["policy"]["template_key"] == "REOPEN_24H"

    def test_offensive_language(self, tenant, contact):
        """Test blocking of offensive words."""
        payload = self._make_payload(tenant, contact, "You are an idiota")
        
        # Act
        response = motor_respond(None, payload)
        
        # Assert
        assert response["decision"]["primary_event"] == "SAFETY_BLOCK"
        assert response["policy"]["block"] is True
        assert response["policy"]["block_reason"] == "INAPPROPRIATE_LANGUAGE"

    def test_llm_failure_fallback(self, mocker, tenant, contact, tenant_event):
        """Test behavior when LLM returns error or invalid JSON."""
        
        mock_llm = mocker.patch("motor_response.api.classify_with_openai")
        mock_llm.return_value = {"ok": False, "error": "API Timeout"}
        
        payload = self._make_payload(tenant, contact, "Hello")
        
        # Act
        response = motor_respond(None, payload)
        
        # Assert
        assert response["decision"]["primary_event"] == "FALLBACK"
        assert response["telemetry"]["llm_error"] == "API Timeout"

    def test_no_events_seeded(self, tenant, contact):
        """Test fallback when no events are configured for tenant."""
        # Ensure no events
        TenantEvent.objects.filter(tenant=tenant).delete()
        
        payload = self._make_payload(tenant, contact, "Hello")
        
        # Act
        response = motor_respond(None, payload)
        
        # Assert
        assert response["decision"]["primary_event"] == "FALLBACK"
        assert response["telemetry"]["reason"] == "NO_EVENTS_SEEDED"
