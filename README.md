# Base de Diseño Minimalista — Motor de Respuesta Reutilizable

Este repositorio contiene una base mínima y estable para implementar un **Motor de Respuesta conversacional** desacoplado del orquestador (ej. n8n), listo para reutilizar en nuevos proyectos.

Incluye:
- Estructura de apps Django: `apps/motor_response` y `apps/whatsapp_inbound`.
- Modelos clave: Tenant, Contact, Conversation, Message, MemoryRecord, Template, TenantEvent, OutboxEvent.
- Endpoint principal: `POST /v1/motor/respond`.
- Contrato de salida estable con `next_actions` deterministas.
- Documentación técnica en `docs/`.

## Uso como plantilla en nuevos proyectos

1) Crear proyecto desde esta base

- Opción A (clonar y renombrar):
  - Clonar el repo
  - Renombrar el paquete/proyecto según tu organización
  - Configurar `.env` y variables del entorno

- Opción B (traer como plantilla de rama):
  - Chequear la rama de plantilla (ej.: `template/minimal-motor-base`)
  - Crear un nuevo repo y hacer `git pull` o `git cherry-pick` desde esa rama

2) Variables y configuración mínima

- Definir `.env` con:
  - `LLM_CLASSIFIER_PROMPT_ID` → ID del Stored Prompt de OpenAI Responses
  - Credenciales necesarias para el orquestador (si aplica)
- Revisar `requirements.txt` y crear entorno virtual (`.venv`)
- Migrar base de datos (`python manage.py migrate`)

3) Endpoints y flujo

- WhatsApp inbound se persiste en `apps/whatsapp_inbound`
- El motor clasifica y decide en `apps/motor_response`
- El orquestador ejecuta las `next_actions` devueltas por el motor

## Guías de referencia

- Diseño y DoD del MVP: [docs/README.md](file:///c:/Users/German/Documents/projects/trae_projects/system-create-json-event-pack/docs/README.md)
- Flujo de salida y acciones: [docs/OUTPUT_FLOW.md](file:///c:/Users/German/Documents/projects/trae_projects/system-create-json-event-pack/docs/OUTPUT_FLOW.md)
- Prompt almacenado y variables: [docs/STORED_PROMPT_REFERENCE.md](file:///c:/Users/German/Documents/projects/trae_projects/system-create-json-event-pack/docs/STORED_PROMPT_REFERENCE.md)
- Plan de pruebas: [docs/TESTING_PLAN.md](file:///c:/Users/German/Documents/projects/trae_projects/system-create-json-event-pack/docs/TESTING_PLAN.md)

## Estructura clave

- Motor: [apps/motor_response](file:///c:/Users/German/Documents/projects/trae_projects/system-create-json-event-pack/apps/motor_response)
- Inbound + Modelos: [apps/whatsapp_inbound](file:///c:/Users/German/Documents/projects/trae_projects/system-create-json-event-pack/apps/whatsapp_inbound)
- Configuración: [config/settings.py](file:///c:/Users/German/Documents/projects/trae_projects/system-create-json-event-pack/config/settings.py)

## Buenas prácticas

- Motor decide; orquestador ejecuta (acciones cerradas).
- Plantillas de WhatsApp mapeadas por `template_key` (fuente de verdad).
- Fallbacks deterministas para 24h cerrada y safety.
- Idempotencia por `turn_wamid` (no duplica efectos).

## Cómo extender

- Agregar eventos por tenant con `TenantEvent` (catálogo de disparadores).
- Añadir plantillas en `Template`.
- Extender lógica del motor en `apps/motor_response/api.py`.

## Licencia y mantenimiento

Esta base está pensada para ser punto de partida. Mantener la compatibilidad del contrato (`schema_version`) al integrarla con orquestadores externos.

