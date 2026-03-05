# Documentación Técnica: Flujo de Salida del Motor de Respuestas

Este documento detalla el funcionamiento técnico del output generado por el endpoint `/v1/motor/respond`, su estructura, procesamiento y el patrón de ejecución esperado.

## 1. Visión General del Flujo

El Motor de Respuestas opera bajo un patrón de **"Decisión Desacoplada"**. El motor *decide* qué hacer, pero no *ejecuta* la acción final (como llamar a la API de WhatsApp). En su lugar, devuelve una lista de instrucciones (`next_actions`) que un orquestador externo debe procesar.

### Diagrama de Flujo de Datos

```mermaid
graph LR
    User(Input Usuario) --> API[API Motor (/respond)]
    API --> Logic{Lógica de Negocio}
    
    Logic -- Ventana > 24h --> ForceT[Forzar Template]
    Logic -- Lenguaje Ofensivo --> Block[Bloqueo de Seguridad]
    Logic -- Ventana Abierta --> AI[Clasificador LLM]
    
    ForceT --> Output
    Block --> Output
    AI --> Output[Construcción JSON]
    
    Output --> Orchestrator((Orquestador Externo))
    
    subgraph "Ejecución (Fuera del Motor)"
        Orchestrator -- Tipo: SEND_MESSAGE --> WA[WhatsApp API]
        Orchestrator -- Tipo: CALL_TEXT_AI --> GPT[Generador de Texto]
        GPT --> WA
    end
```

## 2. Estructura del Output (`MotorRespondOut`)

La respuesta es un objeto JSON estandarizado. El campo crítico para la ejecución es `next_actions`.

### Ejemplo de Payload de Respuesta
```json
{
  "ok": true,
  "tenant_id": "empresa_1",
  "decision": {
    "primary_event": "CONSULTA_PRECIO",
    "confidence": 0.98
  },
  "policy": {
    "response_mode": "FREEFORM"
  },
  "next_actions": [
    {
      "type": "CALL_TEXT_AI",
      "channel": "whatsapp",
      "prompt_key": "GEN_REPLY_V1",
      "input_json": { ... },
      "wa_id": "123456",
      "phone_number_id": "1001"
    }
  ]
}
```

## 3. Tipos de Acciones (`next_actions`)

El orquestador debe manejar los siguientes tipos de acciones definidos en `MotorAction`:

| Tipo | Descripción | Payload Requerido | Acción del Orquestador |
| :--- | :--- | :--- | :--- |
| **`SEND_MESSAGE`** | Enviar un mensaje directo a WhatsApp. | `template_key` (si es template) o `text` (si es texto). | Llamar a la API de Meta/WhatsApp para enviar el mensaje. |
| **`CALL_TEXT_AI`** | Generar una respuesta de texto natural. | `prompt_key`, `input_json`. | Invocar un servicio LLM secundario para redactar la respuesta y luego enviarla. |
| **`HANDOFF`** | Derivar a un humano. | N/A | Marcar la conversación como "pendiente de agente" en el CRM. |

## 4. Lógica de Generación de Salida

El motor implementa reglas estrictas para garantizar el cumplimiento de políticas de WhatsApp y seguridad:

1.  **Filtro de Seguridad**: Si se detectan palabras prohibidas, se vacía la lista de acciones y se reemplaza por un `SEND_MESSAGE` con el template `SAFE_BOUNDARY`.
2.  **Ventana de 24 Horas**:
    *   Si `window_open = False`, se fuerza `response_mode = "TEMPLATE"`.
    *   Si el LLM no sugiere un template válido, el código inyecta automáticamente el template `REOPEN_24H`.
3.  **Modo Freeform**:
    *   Si la política permite texto libre (`FREEFORM`), el motor **nunca** devuelve texto directo en `next_actions`.
    *   Siempre devuelve `CALL_TEXT_AI`. Esto desacopla la *intención* (Motor) de la *redacción* (Text AI).

## 5. Ejemplo de Implementación del Consumidor (Python)

```python
import requests

def process_motor_response(response_json):
    actions = response_json.get("next_actions", [])
    
    for action in actions:
        if action["type"] == "SEND_MESSAGE":
            if action.get("mode") == "template":
                send_whatsapp_template(
                    to=action["wa_id"], 
                    template=action["template_key"]
                )
        
        elif action["type"] == "CALL_TEXT_AI":
            # 1. Generar texto
            generated_text = call_gpt_generator(action["input_json"])
            # 2. Enviar resultado
            send_whatsapp_text(to=action["wa_id"], text=generated_text)

def send_whatsapp_template(to, template):
    print(f"Enviando Template '{template}' a {to}")

def call_gpt_generator(context):
    return "Hola, aquí tienes la información que pediste..."
```

## 6. Métricas de Rendimiento Esperadas

*   **Latencia del Motor**: < 200ms (sin contar LLM) / ~2-4s (con LLM OpenAI).
*   **Tamaño del Payload**: < 5KB promedio.
*   **Tasa de Errores**: < 1% (validado por tests funcionales).

## 7. Manejo de Errores

*   **LLM Caído**: El motor devuelve `primary_event: "FALLBACK"` y una acción por defecto (ej. derivar a humano o mensaje de error genérico), asegurando que el usuario nunca se quede sin respuesta.
*   **Datos Inválidos**: Si el LLM devuelve un JSON roto, el sistema lo atrapa y activa el protocolo de `FALLBACK`.
