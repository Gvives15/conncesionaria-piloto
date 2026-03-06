# Detector de Eventos y Sistema de Reacción (Motor Response)

Este documento detalla la arquitectura, funcionamiento y capacidades del **Motor de Respuesta**, un sistema diseñado para detectar eventos en conversaciones (WhatsApp) y generar reacciones deterministas y accionables.

El sistema opera bajo un paradigma de **"Cerebro Desacoplado"**: el motor decide *qué* hacer (clasificación y estrategia), pero delega *cómo* hacerlo (ejecución técnica) a un orquestador externo (como n8n).

---

## 1. Capacidades del Detector de Eventos y Reacción

El núcleo del sistema es un **clasificador semántico** potenciado por LLM (Large Language Models) que permite:

*   **Detección de Intención Multiclase**: Identifica la intención principal del usuario basándose en un catálogo dinámico de eventos configurables por cliente (`TenantEvent`).
*   **Gestión de Estado Conversacional**: Mantiene un registro de memoria (`MemoryRecord`) con resumen y hechos clave para dar continuidad a la charla.
*   **Reglas de Negocio Críticas**: Aplica filtros de seguridad (lenguaje ofensivo) y reglas de plataforma (ventana de 24h de WhatsApp) antes de procesar la respuesta.
*   **Reacción Determinista**: Transforma la intención detectada en una lista estricta de `next_actions` (acciones siguientes) para garantizar la estabilidad operativa.
*   **Idempotencia**: Garantiza que un mismo mensaje no genere efectos secundarios duplicados, incluso ante reintentos de red.

---

## 2. Arquitectura y Módulos Principales

El proyecto está construido sobre **Django** y estructurado en aplicaciones modulares para separar responsabilidades.

### Estructura de Archivos Relevante

```bash
apps/
├── motor_response/          # Lógica de decisión (Cerebro)
│   ├── api.py               # Endpoint principal y orquestación del flujo
│   ├── llm_classifier.py    # Integración con OpenAI (Stored Prompts)
│   └── schemas.py           # Contratos de datos (Pydantic)
├── whatsapp_inbound/        # Gestión de datos y eventos (Memoria)
│   ├── models.py            # Modelos DB: Tenant, Contact, Message, MemoryRecord
│   └── management/          # Comandos de utilidad (workers, seeders)
└── core/                    # Utilidades compartidas
```

### Módulos Clave

1.  **`motor_response.llm_classifier`**:
    *   Encapsula la llamada a la API de IA.
    *   Utiliza **Stored Prompts** para inyectar contexto de negocio y reglas de clasificación de manera eficiente y segura.
    *   Parsea la respuesta JSON del modelo para extraer `primary_event`, `sentiment`, `risk_level` y `reasoning`.

2.  **`motor_response.api`**:
    *   Controlador principal (`motor_respond`).
    *   Maneja la lógica de **Safety First**: verifica ventana de 24h y contenido ofensivo antes de llamar al LLM.
    *   Implementa el sistema de **Fallbacks**: si el LLM falla, el sistema degrada elegantemente a respuestas predefinidas.

3.  **`whatsapp_inbound.models`**:
    *   **`TenantEvent`**: Catálogo de eventos que el motor puede detectar (ej: "PEDIDO", "CONSULTA_PRECIO").
    *   **`MemoryRecord`**: Persistencia del estado de la conversación por contacto.
    *   **`OutboxEvent`**: Cola de eventos de salida para garantizar la entrega asíncrona (patrón Transactional Outbox).

---

## 3. Funcionamiento Paso a Paso

El ciclo de vida de una detección y reacción es el siguiente:

1.  **Recepción (`POST /v1/motor/respond`)**:
    *   El orquestador envía el mensaje entrante (`turn_wamid`, texto, contacto).
    *   **Validación**: Se verifica si el mensaje ya fue procesado (idempotencia).

2.  **Carga de Contexto**:
    *   Se recupera el perfil del `Tenant` y sus `TenantEvent` activos (caché).
    *   Se carga el `MemoryRecord` del contacto (resumen de charlas previas).

3.  **Pre-Procesamiento (Reglas Duras)**:
    *   **Ventana 24h**: Si pasaron más de 24h desde el último mensaje del usuario, se fuerza una respuesta de plantilla (`REOPEN_24H`).
    *   **Filtro de Seguridad**: Se escanea el texto por palabras ofensivas bloqueantes.

4.  **Detección (LLM)**:
    *   Si pasa las reglas, se construye un prompt JSON con el contexto y el catálogo de eventos.
    *   El LLM clasifica el mensaje y decide la mejor estrategia de respuesta.

5.  **Decisión de Reacción**:
    *   El motor traduce la clasificación del LLM en acciones concretas:
        *   `SEND_MESSAGE`: Enviar un template específico (ej. si la ventana está cerrada).
        *   `DISPATCH_N8N`: Delegar la generación de respuesta compleja al orquestador.
        *   `HANDOFF`: Derivar a un humano si hay riesgo o solicitud explícita.

6.  **Persistencia y Salida**:
    *   Se actualiza la memoria (`MemoryRecord`) con el nuevo evento.
    *   Se devuelve un JSON estructurado con `decision`, `policy` y `next_actions`.

---

## 4. Configuración Requerida

El sistema requiere las siguientes variables de entorno en `.env`:

```ini
# Configuración del Motor
LLM_CLASSIFIER_PROMPT_ID="tu_stored_prompt_id_de_openai"
OPENAI_API_KEY="sk-..."

# Base de Datos
DATABASE_URL="postgres://user:pass@host:port/db"

# Seguridad
SECRET_KEY="django-insecure-..."
DEBUG=False
```

---

## 5. Ejemplos de Implementación

### Caso A: Detección de Intención de Compra

**Entrada (Usuario)**: *"Hola, quiero saber el precio del modelo X"*

**Proceso Interno**:
1.  El motor detecta el evento `CONSULTA_PRECIO` configurado en `TenantEvent`.
2.  Verifica que la ventana de 24h está abierta.
3.  El LLM determina que se requiere información de inventario.

**Salida (JSON)**:
```json
{
  "decision": {
    "primary_event": "CONSULTA_PRECIO",
    "confidence": 0.95,
    "risk_level": "low"
  },
  "next_actions": [
    {
      "type": "DISPATCH_N8N",
      "workflow_key": "WA_REPLY_V1",
      "input_json": { "search_intent": "precio", "model": "X" }
    }
  ]
}
```

### Caso B: Ventana de 24h Cerrada

**Entrada (Usuario)**: *"Hola"* (después de 2 días de inactividad)

**Proceso Interno**:
1.  El motor detecta `window_open: false`.
2.  Ignora la clasificación semántica para evitar fallos de entrega.
3.  Fuerza el uso de una plantilla aprobada por WhatsApp.

**Salida (JSON)**:
```json
{
  "decision": {
    "primary_event": "GREETING",
    "notes": "Force template due to 24h window"
  },
  "next_actions": [
    {
      "type": "SEND_MESSAGE",
      "mode": "template",
      "template_key": "reopen_24h_v1"
    }
  ]
}
```

---

## 6. Casos de Uso Específicos

Este código es ideal para implementar:

1.  **Bots de Venta Automotriz/Inmobiliaria**:
    *   Detección precisa de modelos, versiones y etapas de compra.
    *   Manejo de objeciones mediante `TenantEvent` específicos.

2.  **Soporte Técnico de Nivel 1**:
    *   Clasificación automática de incidentes.
    *   Derivación a humano (`HANDOFF`) basada en detección de frustración (análisis de sentimiento).

3.  **Encuestas y Calificación**:
    *   Extracción de datos estructurados (`facts`) a partir de respuestas libres del usuario.
