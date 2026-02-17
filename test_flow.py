import os
import django
import json
from django.test import Client

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from whatsapp_inbound.models import Tenant, Contact, Conversation, Message, Attribution, MemoryRecord

def test_flow():
    c = Client()
    
    # 1. Caso mínimo: mensaje texto sin referral
    payload_1 = {
        "tenant_id": "concesionaria_001",
        "trace_id": "exec_123",
        "received_at": "2026-02-17T12:00:00Z",
        "channel": "whatsapp",
        "metadata": {
            "provider": "cloud_api",
            "waba_id": None,
            "phone_number_id": "123456",
            "display_phone_number": "+5493510000000"
        },
        "contact": {
            "wa_id": "5493511111111",
            "contact_key": "wa:5493511111111",
            "profile_name": "Juan Perez"
        },
        "message": {
            "wamid": "wamid.HBgL...",
            "timestamp": "2026-02-17T12:00:01Z",
            "type": "text",
            "text": { "body": "Hola, precio del Corolla 2022 y cuotas?" },
            "interactive": None,
            "media": None,
            "raw": { "id": "wamid.HBgL...", "type": "text", "text": { "body": "..." } }
        },
        "referral": None,
        "raw": { "metadata": {}, "contacts": [], "messages": [] }
    }

    print("--- Test Case 1: Text Message ---")
    response = c.post('/v1/whatsapp/inbound', data=payload_1, content_type='application/json')
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    
    assert response.status_code == 200
    
    # Verify DB
    tenant = Tenant.objects.get(name="concesionaria_001")
    contact = Contact.objects.get(tenant=tenant, contact_key="wa:5493511111111")
    message = Message.objects.get(tenant=tenant, wamid="wamid.HBgL...")
    conversation = Conversation.objects.get(tenant=tenant, contact=contact, status="active")
    memory = MemoryRecord.objects.get(tenant=tenant, contact=contact)
    
    print("DB Verification:")
    print(f"Tenant: {tenant.name}")
    print(f"Contact: {contact.profile_name}, {contact.wa_id}")
    print(f"Message: {message.text_body}")
    print(f"Conversation: {conversation.status}")
    print(f"Memory last_msg: {memory.last_user_message_at}")

    # 2. Caso con referral (CTWA)
    payload_2 = {
        "tenant_id": "concesionaria_001",
        "trace_id": "exec_124",
        "received_at": "2026-02-17T12:05:00Z",
        "channel": "whatsapp",
        "metadata": {
            "provider": "cloud_api",
            "phone_number_id": "123456",
            "display_phone_number": "+5493510000000"
        },
        "contact": {
            "wa_id": "5493512222222",
            "contact_key": "wa:5493512222222",
            "profile_name": "Maria"
        },
        "message": {
            "wamid": "wamid.HBgL...2",
            "timestamp": "2026-02-17T12:05:01Z",
            "type": "text",
            "text": { "body": "Buenas, me interesa el Cronos" },
            "raw": { "id": "wamid.HBgL...2", "type": "text" }
        },
        "referral": {
            "source_type": "ad",
            "source_id": "120000000000",
            "ctwa_clid": "AfezXYZ123",
            "headline": "Cronos 0km - cuotas fijas",
            "body": "Tomamos usado, financiá",
            "image_url": "https://..."
        },
        "raw": { "metadata": {}, "contacts": [], "messages": [] }
    }
    
    print("\n--- Test Case 2: Referral Message ---")
    response = c.post('/v1/whatsapp/inbound', data=payload_2, content_type='application/json')
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")

    assert response.status_code == 200

    # Verify Attribution
    contact2 = Contact.objects.get(tenant=tenant, contact_key="wa:5493512222222")
    attribution = Attribution.objects.get(tenant=tenant, contact=contact2, message_wamid="wamid.HBgL...2")
    print("DB Verification:")
    print(f"Attribution source: {attribution.source_type}")
    print(f"Attribution headline: {attribution.headline}")

if __name__ == "__main__":
    test_flow()
