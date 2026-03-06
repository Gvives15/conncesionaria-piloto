# Documentación Técnica: Flujo Completo de Entrada y Salida del Motor LLM

Este documento técnico detalla la arquitectura, flujos de datos y especificaciones para el procesamiento de contexto y generación de respuestas en el sistema de orquestación de mensajes.

## 1. Arquitectura del Sistema

El sistema opera bajo un patrón de **Motor de Decisión Desacoplado**, donde la lógica de clasificación y decisión reside en un servicio API (`motor_response`) que consume servicios de LLM (OpenAI) pero delega la ejecución final a un orquestador externo.

### Componentes Principales
*   **Inbound Handler (`whatsapp_inbound`)**: Normaliza y persiste los mensajes entrantes.
*   **Context Builder (`motor_response`)**: Reconstruye el estado de la conversación desde la base de datos.
*   **LLM Classifier (`llm_classifier.py`)**: Interfaz con OpenAI para la toma de decisiones.
*   **Orquestador (Externo)**: Ejecuta las acciones dictadas por el motor (ej. n8n, worker).

---

## 2. Flujo de Entrada (Input Flow)

El objetivo de esta etapa es construir un objeto JSON rico y estructurado (`classifier_input`) que represente fielmente el estado actual de la conversación para el LLM.

### 2.1 Captura y Validación
1.  **Webhook de WhatsApp**: El mensaje llega crudo desde Meta.
2.  **Normalización**: Se valida contra el esquema `WANormalizedInbound`.
3.  **Persistencia**:
    *   El texto crudo se guarda en `Message.text_body`.
    *   Se actualiza `MemoryRecord.last_user_message_at`.

### 2.2 Construcción del Contexto (Context Builder)
Cuando se invoca `/v1/motor/respond`, el sistema recupera y transforma los datos:

*   **Turno Actual (`turn`)**:
    *   `text_in`: Texto crudo del usuario (incluyendo errores ortográficos).
    *   `timestamp_in`: Hora exacta del mensaje.
*   **Memoria (`memory`)**:
    *   `summary`: Narrativa acumulada de la conversación.
    *   `recent_events`: Lista FIFO de las últimas 20 intenciones detectadas.
    *   `facts_json`: Datos estructurados extraídos (nombre, email, etc.).
*   **Catálogo (`catalog`)**:
    *   `events`: Lista de intenciones configuradas para el tenant (ej. "PEDIDO", "SOPORTE").
    *   `templates`: Plantillas de WhatsApp aprobadas disponibles para uso.
*   **Estado del Sistema (`window`)**:
    *   `window_open`: Booleano calculado (`now - last_message < 24h`).

### 2.3 Ejemplo de Input JSON (Lo que ve el LLM)
```json
{
  "tenant": { "tenant_id": "empresa_1", "domain": "retail" },
  "turn": {
    "text_in": "ola kiero saver presio de las zapatillas",
    "timestamp_in": "2023-10-27T10:00:00Z"
  },
  "window": { "window_open": true },
  "memory": {
    "summary": "Usuario nuevo, saludó anteriormente.",
    "recent_events_json": [{"event": "SALUDO", "confidence": 0.9}]
  },
  "catalog": {
    "events": [{"name": "CONSULTA_PRECIO", "triggers": ["precio"]}],
    "templates": [{"name": "promo_octubre"}]
  }
}
```

---

## 3. Flujo de Salida (Output Flow)

El LLM procesa el input y genera una decisión estructurada que el motor transforma en acciones ejecutables.

### 3.1 Proceso de Generación
1.  **Single Input Variable**: Todo el JSON de entrada se serializa a un string y se inyecta en la variable `{{input_json}}` del Prompt Almacenado en OpenAI.
2.  **Razonamiento del Modelo**: El modelo evalúa la intención, verifica si debe usar un template (si ventana cerrada) o si puede responder libremente.
3.  **Normalización de Respuesta**: El JSON devuelto por OpenAI se valida y completa con valores por defecto si faltan campos.

### 3.2 Formato de Salida (`MotorRespondOut`)
El motor devuelve un "paquete de decisión":

*   **`decision`**: Clasificación semántica (ej. `primary_event: "CONSULTA_PRECIO"`).
*   **`policy`**: Reglas aplicadas (`response_mode: "FREEFORM"` o `"TEMPLATE"`).
*   **`memory_update`**: Nuevos datos para persistir (nuevo `summary`, nuevos `facts`).
*   **`next_actions`**: Lista de instrucciones para el orquestador.

### 3.3 Tipos de Acciones (`next_actions`)
*   **`SEND_MESSAGE`**: Enviar un template específico.
    *   *Uso*: Ventana cerrada, notificaciones, handoff.
*   **`CALL_TEXT_AI`**: Generar respuesta de texto natural.
    *   *Uso*: Conversación fluida (Freeform).
    *   *Nota*: El motor **no** genera el texto final, delega esa tarea a un segundo paso (`GEN_REPLY_V1`).

### 3.4 Ejemplo de Output JSON
```json
{
  "ok": true,
  "decision": { "primary_event": "CONSULTA_PRECIO", "confidence": 0.98 },
  "policy": { "response_mode": "FREEFORM" },
  "next_actions": [
    {
      "type": "CALL_TEXT_AI",
      "prompt_key": "GEN_REPLY_V1",
      "input_json": { "text_in": "...", "primary_event": "CONSULTA_PRECIO" }
    }
  ],
  "memory_update": {
    "summary": "Usuario consultó precio de zapatillas.",
    "active_primary_event": "CONSULTA_PRECIO"
  }
}
```

---

## 4. Criterios de Éxito y Validación

### 4.1 Métricas de Rendimiento
*   **Latencia Técnica**: < 200ms (pre/post procesamiento).
*   **Latencia Total**: < 4s (incluyendo inferencia LLM).
*   **Fiabilidad**: 99.9% de respuestas JSON válidas desde el LLM (gracias a Stored Prompts y reintentos).

### 4.2 Validación de Calidad
*   **Persistencia de Memoria**: Verificar que `summary` evolucione coherentemente turno a turno.
*   **Seguridad**: Bloqueo inmediato de *profanity* sin consumo de tokens LLM.
*   **Cumplimiento 24h**: Tasa del 100% en forzar templates cuando `window_open=false`.

## 5. Troubleshooting Común

| Síntoma | Causa Probable | Solución |
| :--- | :--- | :--- |
| **"Amnesia" del Bot** | `memory_update.summary` no se está guardando en DB. | Verificar commit en `motor_respond/api.py` (Fixed). |
| **Respuesta Vacía** | `next_actions` vacío. | Revisar logs del LLM; posible error de formato JSON. |
| **Bucle de Templates** | Ventana cerrada y falta configuración de templates. | Asegurar que el tenant tenga templates `active=True`. |
| **Error 500 en `/respond`** | OpenAI API Key inválida o Timeout. | Verificar `.env` y logs de latencia. |

## 6. Referencias de Código
*   **Constructor de Input**: [`build_classifier_input`](file:///motor_response/llm_classifier.py)
*   **Lógica de Negocio**: [`motor_respond`](file:///motor_response/api.py)
*   **Esquemas de Datos**: [`schemas.py`](file:///motor_response/schemas.py)
