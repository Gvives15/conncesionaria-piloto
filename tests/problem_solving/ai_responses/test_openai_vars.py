import os
import sys
import json
from openai import OpenAI

# Cargar .env
def load_env_manual():
    try:
        with open('.env', 'r') as f:
            for line in f:
                if '=' in line and not line.strip().startswith('#'):
                    k, v = line.strip().split('=', 1)
                    os.environ[k.strip()] = v.strip('"').strip("'")
    except: pass
load_env_manual()

client = OpenAI()

print("Probando client.responses.create con variables...")

try:
    # Variables de prueba
    vars = {
        "tenant_id": "TEST_TENANT",
        "domain": "test.com",
        "turn_wamid": "wam_123",
        "text_in": "Hola precio",
        "timestamp_in": "2023-01-01",
        "wa_id": "54911",
        "phone_number_id": "1001",
        "window_open": "true",
        "last_user_message_at": "2023-01-01",
        "active_primary_event": "null",
        "active_secondary_events_json": "[]",
        "recent_events_json": "[]",
        "tenant_events_json": "[]"
    }

    # Intento 1: variables dentro de prompt
    response = client.responses.create(
        prompt={
            "id": os.getenv("LLM_CLASSIFIER_PROMPT_ID", "pmpt_69985d2207588190b7913f7099f090e6066e709a927abba6"),
            # "version": "1", # Opcional si es la última
            "variables": vars 
        },
        input=[], # Vacío porque las variables deberían llenar el template
        text={"format": {"type": "text"}},
    )

    print("\n--- RESPUESTA ---")
    print(response.output[0].content[0].text)

except Exception as e:
    print("\n--- ERROR ---")
    print(e)
