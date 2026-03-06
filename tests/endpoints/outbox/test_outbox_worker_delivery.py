import uuid
import pytest
import httpx
from django.core.management import call_command
from whatsapp_inbound.models import OutboxEvent

class DummyResponse:
    def __init__(self, status_code: int, text: str = "OK"):
        self.status_code = status_code
        self.text = text

@pytest.mark.django_db
def test_outbox_worker_delivers_to_n8n(mocker):
    payload = {
        "tenant_id": "test_tenant",
        "contact_key": "wa:549112334455",
        "wa_id": "54911223347455",
        "phone_number_id": "1001",
        "turn_wamid": f"wamid.test.{uuid.uuid4()}",
        "text": "Hola, prueba outbox",
        "timestamp_in": "2024-01-01T00:00:00Z",
        "channel": "whatsapp",
    }
    evt = OutboxEvent.objects.create(
        topic=OutboxEvent.TOPIC_INBOUND_SAVED,
        tenant_id=payload["tenant_id"],
        contact_key=payload["contact_key"],
        turn_wamid=payload["turn_wamid"],
        dedupe_key=f"test_{uuid.uuid4()}",
        payload_json=payload,
        status=OutboxEvent.STATUS_PENDING,
    )

    called = {}

    def fake_post(url, json, headers):
        called["url"] = url
        called["json"] = json
        called["headers"] = headers
        return DummyResponse(200, "ok")

    mocker.patch.object(httpx.Client, "post", side_effect=fake_post)

    call_command("run_outbox_worker", "--once")

    refreshed = OutboxEvent.objects.get(id=evt.id)
    assert refreshed.status == OutboxEvent.STATUS_SENT
    assert called["json"] == payload
    assert called["headers"]["X-Topic"] == OutboxEvent.TOPIC_INBOUND_SAVED
    assert "X-Outbox-Event-Id" in called["headers"]
