
import os
import httpx
import json
import time

# Payload simplificado (lo que envía el Inbound a n8n)
payload = {
    "tenant_id": "distri_cig_001",
    "contact_key": "wa:5491198765432",
    "wa_id": "5491198765432",
    "phone_number_id": "100987654321",
    "turn_wamid": f"wamid.MANUAL_TEST_{int(time.time())}",
    "text": "Hola, prueba manual directa a n8n",
    "timestamp_in": "2024-05-20T10:30:00Z",
    "channel": "whatsapp"
}

target_url = os.getenv("N8N_WEBHOOK_URL", "http://n8n:5678/webhook/worker")

print(f"Payload a enviar:\n{json.dumps(payload, indent=2)}")

print(f"\n--- Enviando a N8N_WEBHOOK_URL: {target_url} ---")
try:
    resp = httpx.post(target_url, json=payload, timeout=10.0)
    print(f"Status: {resp.status_code}")
    print(f"Response: {resp.text}")
    if resp.status_code == 200:
        print("✅ ÉXITO: Webhook respondió 200")
    else:
        print("❌ FALLO: Webhook respondió distinto de 200")
except Exception as e:
    print(f"⚠️ ERROR DE CONEXIÓN: {e}")
