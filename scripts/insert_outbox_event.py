import os
import django
import json
import uuid
from datetime import datetime

# Setup Django environment
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from whatsapp_inbound.models import OutboxEvent

def insert_real_event():
    # Este es el payload JSON exacto que el sistema espera enviar a n8n
    # Incluye toda la info del mensaje y el contexto
    payload = {
        "tenant_id": "distri_cig_001",
        "contact_key": "wa:5491122334455",
        "wa_id": "5491122334455",
        "phone_number_id": "1001",
        "turn_wamid": f"wamid.HBgMNTQ5MTEyMjMzNDQ1NRUCABIIIGNlMmU0YmRkLWRhMmQtNGQzMy1iZTVlLTAzM2EwZGY1AA==.{uuid.uuid4()}",
        "text": "Hola, me pasas la lista de precios de cigarrillos?",
        "timestamp_in": datetime.now().isoformat(),
        "channel": "whatsapp",
        # Metadata extra que podría ser útil para n8n
        "metadata": {
            "source": "manual_test",
            "priority": "high"
        }
    }

    event = OutboxEvent.objects.create(
        topic=OutboxEvent.TOPIC_INBOUND_SAVED,
        tenant_id=payload["tenant_id"],
        contact_key=payload["contact_key"],
        turn_wamid=payload["turn_wamid"],
        dedupe_key=f"manual_insert_{uuid.uuid4()}",
        payload_json=payload,
        status=OutboxEvent.STATUS_PENDING  # Importante: 'pending' para que el worker lo tome
    )
    
    print(f"🚀 Evento insertado en OutboxEvent:")
    print(f"   ID: {event.id}")
    print(f"   Status: {event.status}")
    print(f"   Payload: {json.dumps(payload, indent=2)}")

if __name__ == "__main__":
    insert_real_event()
