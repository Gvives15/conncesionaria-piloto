import os
import time
import json
import httpx

URL = os.getenv("INBOUND_URL", "http://motorapi:8000/v1/whatsapp/inbound")

payload = {
    "tenant_id": "test_tenant",
    "trace_id": f"trace_{int(time.time())}",
    "received_at": "2023-10-27T10:00:00Z",
    "channel": "whatsapp",
    "metadata": {
        "provider": "cloud_api",
        "display_phone_number": "1234567890",
        "phone_number_id": "1001"
    },
    "contact": {
        "wa_id": "5491122334455",
        "contact_key": "wa:5491122334455",
        "profile_name": "Test User"
    },
    "message": {
        "wamid": f"wamid_e2e_{int(time.time())}",
        "timestamp": "2023-10-27T10:00:00Z",
        "type": "text",
        "text": {"body": "Hola, prueba e2e inbound"},
        "raw": {}
    },
    "raw": {}
}

print(f"Sending inbound to: {URL}")
print(json.dumps(payload, indent=2))

try:
    r = httpx.post(URL, json=[payload], timeout=10.0)
    print("Status:", r.status_code)
    print("Body:", r.text[:500])
except Exception as e:
    print("ERROR:", e)

# Verify OutboxEvent status for this wamid
try:
    import django
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    django.setup()
    from whatsapp_inbound.models import OutboxEvent
    wamid = payload["message"]["wamid"]
    evt = OutboxEvent.objects.filter(turn_wamid=wamid).order_by("-created_at").first()
    if evt:
        print(f"OutboxEvent found: id={evt.id}, status={evt.status}, topic={evt.topic}")
    else:
        print("OutboxEvent not found for this wamid.")
except Exception as e:
    print("ERROR checking OutboxEvent:", e)
