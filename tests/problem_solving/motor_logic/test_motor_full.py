import os
import sys
import json
import django
from datetime import timedelta

# Configuración de Django
sys.path.append(os.getcwd())
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "scripts.temp_settings")
django.setup()

from django.utils import timezone
from motor_response.api import motor_respond
from motor_response.schemas import MotorRespondIn
from whatsapp_inbound.models import Tenant, Contact, Template, TenantEvent

# Cargar .env para asegurarnos de tener la API KEY
def load_env_manual():
    try:
        with open('.env', 'r') as f:
            for line in f:
                if '=' in line and not line.strip().startswith('#'):
                    k, v = line.strip().split('=', 1)
                    os.environ[k.strip()] = v.strip('"').strip("'")
    except: pass
load_env_manual()

def run_test():
    print("--- INICIANDO TEST DE MOTOR RESPONSE ---")
    
    # 1. Crear datos de prueba
    tenant_id = "TEST_TENANT_ABC"
    tenant, _ = Tenant.objects.get_or_create(
        tenant_key=tenant_id, 
        defaults={"domain": "test.com", "business_name": "Test Business"}
    )
    
    # Crear un evento de prueba en el catálogo
    # Corrigiendo nombres de campos según error de Django
    TenantEvent.objects.get_or_create(
        tenant=tenant,
        name="CONSULTA_PRECIO", # Antes event_name
        defaults={
            # "description": "Cliente pregunta precio", # Campo no existe en modelo
            "triggers": ["precio", "cuanto sale", "costo"], # Antes keywords
            "is_active": True # Antes active
        }
    )

    # Crear contacto
    contact_key = "wa:5491122334455"
    contact, _ = Contact.objects.get_or_create(
        tenant=tenant,
        contact_key=contact_key,
        defaults={"wa_id": "5491122334455"} # 'name' no existe en Contact
    )

    # 2. Preparar payload de entrada (simulando request HTTP)
    payload = MotorRespondIn(
        tenant_id=tenant_id,
        contact_key=contact_key,
        turn_wamid="wamid.HBgLTEST123",
        text="Hola, cual es el precio?", # Mensaje del usuario
        timestamp_in=timezone.now().isoformat(),
        channel="whatsapp",
        wa_id="5491122334455",
        phone_number_id="100100100"
    )

    print(f"Enviando mensaje: '{payload.text}'")
    print("Llamando a motor_respond (esto usará OpenAI)...")

    # 3. Ejecutar motor
    try:
        # Simulamos request=None porque motor_respond no usa 'request' realmente
        response = motor_respond(None, payload)
        
        # motor_respond devuelve un dict si usamos django-ninja sin la api completa, 
        # pero en realidad el router de django-ninja se encarga de convertir el dict a schema.
        # Al llamar la función directamente, devuelve lo que devuelve la función: un dict (o objeto pydantic si lo definimos así).
        # Revisemos api.py: devuelve 'out' que es un dict.
        
        print("\n--- RESULTADO DEL MOTOR ---")
        if isinstance(response, dict):
            print(f"OK: {response.get('ok')}")
            decision = response.get('decision', {})
            policy = response.get('policy', {})
            next_actions = response.get('next_actions', [])
            
            print(f"Evento Detectado: {decision.get('primary_event')}")
            print(f"Confianza: {decision.get('confidence')}")
            print(f"Modo Respuesta: {policy.get('response_mode')}")
            
            print("\nAcciones:")
            for action in next_actions:
                # action es un dict aquí
                tipo = action.get('type') or action.get('action') # LLM devuelve 'action', motor normaliza a 'type'? Revisar api.py
                print(f"- Tipo: {tipo}")
                if tipo == "SEND_MESSAGE":
                     mode = action.get('mode')
                     print(f"  Modo: {mode}")
                     if mode == "freeform":
                         print(f"  Texto: {action.get('text')}")
                     elif mode == "template":
                         print(f"  Template: {action.get('template_key')}")
                elif tipo == "CALL_TEXT_AI":
                     print(f"  Params: {action.get('parameters')}")
        else:
            # Si fuera objeto Pydantic
            print(f"OK: {response.ok}")
            print(f"Evento Detectado: {response.decision.primary_event}")
            print(f"Confianza: {response.decision.confidence}")
            print(f"Modo Respuesta: {response.policy.response_mode}")


    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_test()
