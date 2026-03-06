import uuid
import pytest
from whatsapp_inbound.models import OutboxEvent

@pytest.mark.django_db
def test_insert_outbox_event_json():
    payload = {
        "tenant_id": "test_tenant",
        "contact_key": "wa:549112334455",
        "wa_id": "54911223347455",
        "phone_number_id": "1001",
        "turn_wamid": f"wamid.test.{uuid.uuid4()}",
        "text": "Hola, prueba outbox",
        "timestamp_in": "2024-01-01T00:00:00Z",
        "channel": "whatsapp"
    }
    evt = OutboxEvent.objects.create(
        topic=OutboxEvent.TOPIC_INBOUND_SAVED,
        tenant_id=payload["tenant_id"],
        contact_key=payload["contact_key"],
        turn_wamid=payload["turn_wamid"],
        dedupe_key=f"test_{uuid.uuid4()}",
        payload_json=payload,
        status=OutboxEvent.STATUS_PENDING
    )
    assert evt.status == OutboxEvent.STATUS_PENDING
    assert evt.payload_json == payload
    assert evt.topic == OutboxEvent.TOPIC_INBOUND_SAVED
