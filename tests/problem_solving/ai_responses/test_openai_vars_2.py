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

vars = {
    "tenant_id": "TEST_TENANT",
    "domain": "test.com",
    "turn_wamid": "wam_123",
    "text_in": "Hola precio",
    "timestamp_in": "2023-01-01",
    "wa_id": "54911",
    "phone_number_id": "1001",
    "window_open": True,
    "last_user_message_at": "2023-01-01",
    "active_primary_event": "null",
    "active_secondary_events": [], # Ojo, en JSON debe ser string o lista?
    "active_secondary_events_json": "[]",
    "recent_events": [],
    "recent_events_json": "[]",
    "tenant_events": [],
    "tenant_events_json": "[]"
}

print("Probando client.responses.create con variables top-level...")

try:
    # Intento 2: variables como argumento directo (si la librería lo soporta)
    # Nota: Si esto falla, Python lanzará TypeError
    try:
        response = client.responses.create(
            prompt={
                "id": os.getenv("LLM_CLASSIFIER_PROMPT_ID", "pmpt_69985d2207588190b7913f7099f090e6066e709a927abba6")
            },
            variables=vars, # Argumento hipotético
            input=[], 
            text={"format": {"type": "text"}},
        )
        print("--- ÉXITO con variables=... ---")
        print(response.output[0].content[0].text)
    except TypeError as e:
        print(f"Falló variables=...: {e}")

    # Intento 3: input como diccionario de variables
    # Si input acepta lista de mensajes, quizás acepta dict de variables si es prompt template
    try:
        print("\nProbando input=dict...")
        response = client.responses.create(
            prompt={
                "id": os.getenv("LLM_CLASSIFIER_PROMPT_ID", "pmpt_69985d2207588190b7913f7099f090e6066e709a927abba6")
            },
            input=[vars], # Lista con un dict? O input=vars? Probemos lista con dict (Messages?)
            # Si vars es un dict, no cumple con Message(role, content). 
            # Pero probemos si acepta variables planas.
            text={"format": {"type": "text"}},
        )
        print("--- ÉXITO con input=[dict] ---")
        print(response.output[0].content[0].text)
    except Exception as e:
        print(f"Falló input=[dict]: {e}")

except Exception as e:
    print(f"\n--- ERROR GENERAL --- {e}")
