
import httpx
import json
import time

# Mock payload matching WANormalizedInbound schema
payload = {
    "tenant_id": "test_tenant",
    "trace_id": f"trace_{int(time.time())}",
    "received_at": "2023-10-27T10:00:00Z",
    "channel": "whatsapp",
    "metadata": {
        "provider": "cloud_api",
        "display_phone_number": "1234567890"
    },
    "contact": {
        "wa_id": "5491122334455",
        "contact_key": "5491122334455",
        "profile_name": "Test User"
    },
    "message": {
        "wamid": f"wamid_{int(time.time())}",
        "timestamp": "2023-10-27T10:00:00Z",
        "type": "text",
        "text": {
            "body": "Hola, esto es una prueba de inbound"
        },
        "raw": {}
    },
    "raw": {}
}

url = "http://localhost:8000/v1/whatsapp/inbound"

print(f"Sending POST to {url}...")
try:
    response = httpx.post(url, json=payload, timeout=10)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text}")
    
    if response.status_code == 200:
        print("SUCCESS: Inbound processed correctly.")
    else:
        print("FAILURE: Inbound failed.")

except Exception as e:
    print(f"ERROR: {e}")
