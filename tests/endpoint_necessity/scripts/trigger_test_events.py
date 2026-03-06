
import httpx
import json
import time
import uuid
import random
from datetime import datetime, timezone

# URL del Inbound (que luego enviará a n8n)
URL = "http://localhost:8000/v1/whatsapp/inbound"

# Textos de prueba variados
TEST_MESSAGES = [
    "Hola, quiero saber precios de cigarrillos",
    "Tienen Marlboro Box?",
    "Me pasas la lista de precios actualizada?",
    "Donde queda el deposito para retirar?",
    "Aceptan transferencia?",
    "Quiero hacer un pedido grande",
    "Tienen stock de Philip Morris?",
    "Gracias, muy amables",
    "Hola",
    "Precio del Lucky Strike",
    "puta mierda" # Test de filtro de seguridad
]

TENANT_ID = "distri_cig_001"
CONTACT_WA_ID = "5491198765432"
PHONE_NUMBER_ID = "100987654321"

def generate_payload(text):
    now_ts = datetime.now(timezone.utc).isoformat()
    # Unique IDs
    wamid = f"wamid.{uuid.uuid4()}"
    trace_id = f"exec_{uuid.uuid4()}"
    
    return {
        "tenant_id": TENANT_ID,
        "trace_id": trace_id,
        "received_at": now_ts,
        "channel": "whatsapp",
        "metadata": {
            "provider": "cloud_api",
            "waba_id": "100123456789",
            "phone_number_id": PHONE_NUMBER_ID,
            "display_phone_number": "5491112345678"
        },
        "contact": {
            "wa_id": CONTACT_WA_ID,
            "contact_key": f"wa:{CONTACT_WA_ID}",
            "profile_name": "Usuario Test"
        },
        "message": {
            "wamid": wamid,
            "timestamp": now_ts,
            "type": "text",
            "text": {
                "body": text
            },
            "raw": {
                "from": CONTACT_WA_ID,
                "id": wamid,
                "timestamp": str(int(time.time())),
                "text": {"body": text},
                "type": "text"
            }
        },
        "referral": None,
        "raw": {} # Raw simplificado
    }

def run_tests():
    print(f"--- Iniciando envío de {len(TEST_MESSAGES)} eventos de prueba ---")
    
    for i, text in enumerate(TEST_MESSAGES):
        payload = generate_payload(text)
        print(f"\n[{i+1}/{len(TEST_MESSAGES)}] Enviando: '{text}'")
        
        try:
            # Enviamos al Inbound local
            resp = httpx.post(URL, json=payload, timeout=10.0)
            
            if resp.status_code == 200:
                print(f"✅ OK - Inbound procesado. Respuesta: {resp.json()}")
            else:
                print(f"❌ ERROR - Status: {resp.status_code}. Body: {resp.text}")
                
        except Exception as e:
            print(f"⚠️ EXCEPTION: {e}")
            
        # Esperar un poco entre mensajes para no saturar y ver logs ordenados
        time.sleep(1)

if __name__ == "__main__":
    run_tests()
