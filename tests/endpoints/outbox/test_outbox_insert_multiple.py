import uuid
import pytest
from django.db import IntegrityError
from whatsapp_inbound.models import OutboxEvent

@pytest.mark.django_db
def test_insert_multiple_outbox_events_and_query():
    payload1 = {
        "tenant_id": "test_tenant_1",
        "contact_key": "wa:5491111111111",
        "wa_id": "5491111111111",
        "phone_number_id": "1001",
        "turn_wamid": f"wamid.test.{uuid.uuid4()}",
        "text": "Hola 1",
        "timestamp_in": "2024-01-01T00:00:00Z",
        "channel": "whatsapp"
    }
    payload2 = {
        "tenant_id": "test_tenant_2",
        "contact_key": "wa:5491222222222",
        "wa_id": "5491222222222",
        "phone_number_id": "1002",
        "turn_wamid": f"wamid.test.{uuid.uuid4()}",
        "text": "Hola 2",
        "timestamp_in": "2024-01-02T00:00:00Z",
        "channel": "whatsapp"
    }
    e1 = OutboxEvent.objects.create(
        topic=OutboxEvent.TOPIC_INBOUND_SAVED,
        tenant_id=payload1["tenant_id"],
        contact_key=payload1["contact_key"],
        turn_wamid=payload1["turn_wamid"],
        dedupe_key=f"test_multi_{uuid.uuid4()}",
        payload_json=payload1,
        status=OutboxEvent.STATUS_PENDING
    )
    e2 = OutboxEvent.objects.create(
        topic=OutboxEvent.TOPIC_INBOUND_SAVED,
        tenant_id=payload2["tenant_id"],
        contact_key=payload2["contact_key"],
        turn_wamid=payload2["turn_wamid"],
        dedupe_key=f"test_multi_{uuid.uuid4()}",
        payload_json=payload2,
        status=OutboxEvent.STATUS_PENDING
    )
    qs = OutboxEvent.objects.filter(status=OutboxEvent.STATUS_PENDING)
    assert qs.count() >= 2
    ids = set(qs.values_list("id", flat=True))
    assert e1.id in ids and e2.id in ids

@pytest.mark.django_db
def test_outbox_dedupe_key_uniqueness():
    payload = {
        "tenant_id": "dup_tenant",
        "contact_key": "wa:5491333333333",
        "wa_id": "5491333333333",
        "phone_number_id": "1003",
        "turn_wamid": f"wamid.test.{uuid.uuid4()}",
        "text": "Hola dup",
        "timestamp_in": "2024-01-03T00:00:00Z",
        "channel": "whatsapp"
    }
    dedupe = f"dup_{uuid.uuid4()}"
    OutboxEvent.objects.create(
        topic=OutboxEvent.TOPIC_INBOUND_SAVED,
        tenant_id=payload["tenant_id"],
        contact_key=payload["contact_key"],
        turn_wamid=payload["turn_wamid"],
        dedupe_key=dedupe,
        payload_json=payload,
        status=OutboxEvent.STATUS_PENDING
    )
    with pytest.raises(IntegrityError):
        OutboxEvent.objects.create(
            topic=OutboxEvent.TOPIC_INBOUND_SAVED,
            tenant_id=payload["tenant_id"],
            contact_key=payload["contact_key"],
            turn_wamid=payload["turn_wamid"],
            dedupe_key=dedupe,
            payload_json=payload,
            status=OutboxEvent.STATUS_PENDING
        )
