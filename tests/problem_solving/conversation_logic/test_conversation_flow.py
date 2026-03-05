import os
import sys
import json
import django
import uuid
import time
from datetime import timedelta
from typing import List, Dict, Any

# Configuración de Django
sys.path.append(os.getcwd())
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.utils import timezone
from motor_response.api import motor_respond
from motor_response.schemas import MotorRespondIn
from whatsapp_inbound.models import Tenant, Contact, TenantEvent, Template

# Colores para la consola
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

# Cargar .env manualmente
def load_env_manual():
    try:
        with open('.env', 'r') as f:
            for line in f:
                if '=' in line and not line.strip().startswith('#'):
                    k, v = line.strip().split('=', 1)
                    os.environ[k.strip()] = v.strip('"').strip("'")
    except: pass
load_env_manual()

class ConversationTester:
    def __init__(self, tenant_id: str = "TEST_TENANT_FLOW"):
        self.tenant_id = tenant_id
        self.contact_key = f"wa:{int(time.time())}" # Contacto único por ejecución
        self.wa_id = self.contact_key.replace("wa:", "")
        self.setup_data()
        self.results = []
        
    def setup_data(self):
        print(f"{Colors.HEADER}--- SETUP: Creando datos de prueba ---{Colors.ENDC}")
        self.tenant, _ = Tenant.objects.get_or_create(
            tenant_key=self.tenant_id,
            defaults={"domain": "flow-test.com", "business_name": "Flow Test Business"}
        )
        
        # 1. Evento: Consulta de Precio
        TenantEvent.objects.get_or_create(
            tenant=self.tenant,
            name="CONSULTA_PRECIO",
            defaults={"triggers": ["precio", "cuanto sale", "costo"], "is_active": True}
        )
        
        # 2. Evento: Soporte Humano (Handoff)
        # El modelo TenantEvent no tiene campo 'handoff'.
        # Usaremos triggers para que el LLM detecte la intención y las reglas del prompt hagan el resto.
        # Si queremos indicar handoff, quizás sea un campo en triggers o un nombre específico.
        # Por ahora lo dejamos como evento normal, el prompt en OpenAI debería tener la regla:
        # "Si es SOPORTE_HUMANO => handoff=true" (o lo agregamos en triggers como metadata si el modelo lo soporta)
        TenantEvent.objects.get_or_create(
            tenant=self.tenant,
            name="SOPORTE_HUMANO",
            defaults={"triggers": ["humano", "asesor", "persona"], "is_active": True}
        )
        
        # 3. Template: Reopen Window
        Template.objects.get_or_create(
            tenant=self.tenant,
            name="reopen_24h_v1",
            defaults={
                "category": "UTILITY",
                "language": "es",
                "components_json": [{"type": "BODY", "text": "Hola, para continuar la charla responde a este mensaje."}],
                "active": True
            }
        )
        
        # Contacto
        Contact.objects.get_or_create(
            tenant=self.tenant,
            contact_key=self.contact_key,
            defaults={"wa_id": self.wa_id}
        )
        print(f"{Colors.OKGREEN}✓ Datos creados para {self.contact_key}{Colors.ENDC}\n")

    def run_step(self, step_name: str, input_text: str, expected_event: str, 
                 window_open: bool = True, expected_mode: str = "FREEFORM",
                 accepted_events: List[str] = None):
        
        print(f"{Colors.BOLD}>>> Paso: {step_name}{Colors.ENDC}")
        print(f"    Input: '{input_text}' (Window: {window_open})")
        
        if not window_open:
            from whatsapp_inbound.models import MemoryRecord
            mem = MemoryRecord.objects.filter(tenant=self.tenant, contact__contact_key=self.contact_key).first()
            if mem:
                mem.last_user_message_at = timezone.now() - timedelta(hours=25)
                mem.save()
                print(f"    {Colors.WARNING}[!] Forzando ventana cerrada en DB{Colors.ENDC}")

        payload = MotorRespondIn(
            tenant_id=self.tenant_id,
            contact_key=self.contact_key,
            turn_wamid=f"wamid.{uuid.uuid4()}",
            text=input_text,
            timestamp_in=timezone.now().isoformat(),
            channel="whatsapp",
            wa_id=self.wa_id,
            phone_number_id="100100100"
        )

        start_time = time.time()
        try:
            response = motor_respond(None, payload)
            duration = time.time() - start_time
            
            # Normalizar respuesta (puede ser dict o objeto)
            if not isinstance(response, dict):
                response = response.dict()
            
            decision = response.get('decision', {})
            policy = response.get('policy', {})
            
            actual_event = decision.get('primary_event')
            actual_mode = policy.get('response_mode')
            confidence = decision.get('confidence')
            
            # Validación
            # Permitir lista de eventos aceptados para flexibilidad contextual
            if accepted_events:
                event_match = actual_event in accepted_events or actual_event == expected_event
            else:
                event_match = actual_event == expected_event
                
            mode_match = actual_mode == expected_mode
            passed = event_match and mode_match
            
            result = {
                "step": step_name,
                "input": input_text,
                "expected": {"event": expected_event, "mode": expected_mode},
                "actual": {"event": actual_event, "mode": actual_mode, "conf": confidence},
                "passed": passed,
                "duration": f"{duration:.2f}s"
            }
            self.results.append(result)
            
            if passed:
                print(f"    {Colors.OKGREEN}✓ PASSED{Colors.ENDC} -> Event: {actual_event} ({confidence}) | Mode: {actual_mode}")
            else:
                print(f"    {Colors.FAIL}✗ FAILED{Colors.ENDC}")
                print(f"      Expected: {expected_event} (or {accepted_events}) / {expected_mode}")
                print(f"      Actual:   {actual_event} / {actual_mode}")
                
            return passed

        except Exception as e:
            print(f"    {Colors.FAIL}ERROR CRITICO: {e}{Colors.ENDC}")
            self.results.append({"step": step_name, "passed": False, "error": str(e)})
            return False

    def print_report(self):
        print(f"\n{Colors.HEADER}=== REPORTE FINAL DE COBERTURA ==={Colors.ENDC}")
        print(f"{'PASO':<35} | {'RESULTADO':<10} | {'TIEMPO':<10} | {'DETALLE'}")
        print("-" * 90)
        
        passed_count = 0
        for r in self.results:
            status = "PASS" if r.get("passed") else "FAIL"
            color = Colors.OKGREEN if r.get("passed") else Colors.FAIL
            
            # Detalle mejorado: Evento detectado y modo de respuesta
            actual = r.get('actual', {})
            event = actual.get('event') or "None"
            mode = actual.get('mode') or "None"
            conf = actual.get('conf') or 0.0
            
            detail = f"{event[:20]:<20} ({conf:.2f}) [{mode}]"
            
            print(f"{r['step']:<35} | {color}{status:<10}{Colors.ENDC} | {r.get('duration', 'N/A'):<10} | {detail}")
            if r.get("passed"): passed_count += 1
            
        success_rate = (passed_count / len(self.results)) * 100
        print("-" * 90)
        
        # Color del resumen final
        rate_color = Colors.OKGREEN if success_rate == 100 else (Colors.WARNING if success_rate >= 60 else Colors.FAIL)
        print(f"Total: {len(self.results)} | Pasaron: {passed_count} | Tasa de Éxito: {rate_color}{success_rate:.1f}%{Colors.ENDC}")
        
        # Guardar reporte en archivo
        try:
            with open("test_report.json", "w") as f:
                json.dump(self.results, f, indent=2, default=str)
            print(f"\n{Colors.OKBLUE}Reporte guardado en test_report.json{Colors.ENDC}")
        except Exception as e:
            print(f"{Colors.WARNING}No se pudo guardar el reporte JSON: {e}{Colors.ENDC}")

def main():
    tester = ConversationTester()
    
    # --- MATRIZ DE PRUEBAS ---
    
    # 1. Inicio de Conversación (Contexto vacío)
    tester.run_step(
        step_name="1. Inicio - Saludo/Precio",
        input_text="Hola, cual es el precio?",
        expected_event="CONSULTA_PRECIO",
        expected_mode="FREEFORM"
    )
    
    # 2. Continuidad (Contexto previo debería influir)
    # El usuario pregunta algo ambiguo, pero por contexto debería ser precio
    tester.run_step(
        step_name="2. Continuidad - Pregunta corta",
        input_text="y el costo de envio?",
        expected_event="CONSULTA_PRECIO", 
        expected_mode="FREEFORM"
    )
    
    # 3. Handoff (Derivación a humano)
    # ACTUALIZADO: Esperamos TEMPLATE según nueva regla de system prompt
    tester.run_step(
        step_name="3. Handoff - Pedir humano",
        input_text="quiero hablar con alguien",
        expected_event="SOPORTE_HUMANO",
        expected_mode="TEMPLATE" 
    )
    
    # 4. Seguridad (Insulto)
    tester.run_step(
        step_name="4. Seguridad - Insulto",
        input_text="son una estafa y una mierda",
        expected_event="SAFETY_BLOCK",
        expected_mode="TEMPLATE"
    )
    
    # 5. Ventana Cerrada (Simulación > 24h)
    # ACTUALIZADO: Aceptamos CONSULTA_PRECIO o SOPORTE_HUMANO, lo vital es el modo TEMPLATE
    tester.run_step(
        step_name="5. Ventana Cerrada - Reintento",
        input_text="hola sigo esperando",
        expected_event="CONSULTA_PRECIO",
        accepted_events=["SOPORTE_HUMANO", "CONSULTA_PRECIO", "FALLBACK"], # Flexibilidad contextual
        window_open=False,
        expected_mode="TEMPLATE" # Obligatorio
    )

    tester.print_report()

if __name__ == "__main__":
    main()
