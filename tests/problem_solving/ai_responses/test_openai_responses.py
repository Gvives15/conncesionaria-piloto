import os
import sys
import json
from openai import OpenAI

# Cargar .env manualmente
def load_env_manual():
    try:
        with open('.env', 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' in line:
                    key, value = line.split('=', 1)
                    value = value.strip()
                    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
                        value = value[1:-1]
                    os.environ[key.strip()] = value
    except FileNotFoundError:
        print("No se encontró el archivo .env")

load_env_manual()

client = OpenAI()

print("Probando client.responses.create...")

try:
    # Datos de prueba simulando lo que enviaría el sistema
    dummy_input = {
        "text": "Hola, precio?",
        "context": "test"
    }
    input_str = json.dumps(dummy_input)

    # Intento de llamada con el código del usuario
    # Asumimos que input debe llevar el contenido del usuario si el prompt lo espera,
    # O si el prompt tiene variables, tal vez la API espera un dict de variables?
    # Como no hay documentación clara de 'responses' (beta?), probaremos input como lista de mensajes
    # o input vacío para ver qué error da si faltan variables.
    
    response = client.responses.create(
        prompt={
            "id": os.getenv("LLM_CLASSIFIER_PROMPT_ID", "pmpt_69985d2207588190b7913f7099f090e6066e709a927abba6"),
            "version": "1"
        },
        input=[
            # Probamos enviar el input como un mensaje de usuario, 
            # asumiendo que se añade al contexto o resuelve variables si es inteligente.
            # Si el prompt espera variables {{}}, esto podría fallar.
            {
                "role": "user",
                "content": input_str
            }
        ],
        text={
            "format": {
                "type": "text" # El usuario puso text, pero quizás queremos json_object si el prompt lo dice
            }
        },
        max_output_tokens=2048,
    )

    print("\n--- RESPUESTA ---")
    print(response)

except Exception as e:
    print("\n--- ERROR ---")
    print(e)
