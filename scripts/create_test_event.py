import os
import django
import json
import uuid
from datetime import datetime

# Setup Django environment
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from whatsapp_inbound.models import OutboxEvent

def create_test_event():
    # Datos de prueba simulando un mensaje real de WhatsApp
    payload = {
        "tenant_id": "test_tenant",
        "contact_key": "wa:5491122334455",
        "wa_id": "5491122334455",
        "phone_number_id": "1001",
        "turn_wamid": f"wamid.test.{uuid.uuid4()}",
        "text": "Hola, quiero probar el worker",
        "timestamp_in": datetime.now().isoformat(),
        "channel": "whatsapp"
    }

    event = OutboxEvent.objects.create(
        topic=OutboxEvent.TOPIC_INBOUND_SAVED,
        tenant_id=payload["tenant_id"],
        contact_key=payload["contact_key"],
        turn_wamid=payload["turn_wamid"],
        dedupe_key=f"test_dedupe_{uuid.uuid4()}",
        payload_json=payload,
        status=OutboxEvent.STATUS_PENDING
    )
    
    print(f"✅ Evento de prueba creado con ID: {event.id}")
    print(f"   Estado: {event.status}")
    print(f"   Payload: {json.dumps(payload, indent=2)}")

if __name__ == "__main__":
    create_test_event()
