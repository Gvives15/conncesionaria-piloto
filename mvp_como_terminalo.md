# Motor Response — MVP Definition of Done (DoD) y objetivo “Producto Usable”

Este README define con precisión **qué significa “terminar el MVP”** del Motor Response y **qué condiciones tienen que cumplirse** para considerarlo un producto usable (estable para operar con n8n + WhatsApp).

La idea central del MVP es:  
**Motor = decide (intención + política). n8n = ejecuta (IA de texto, búsquedas, envíos, efectos).**  
El sistema debe ser estable aun cuando el LLM falle.

---

## 1) Objetivo del MVP

Convertir cada mensaje entrante (WhatsApp inbound) en una **respuesta accionable y consistente** para que el orquestador (n8n) la ejecute, usando:

- Contrato JSON **estable** (sin sorpresas).
- Reglas de negocio mínimas (24h, safety, fallbacks).
- Acciones **macro** (pocas y claras).
- Fallbacks deterministas para que el pipeline **nunca quede en limbo**.

---

## 2) Decisión central del MVP (cerrada)

En el MVP, el LLM **NO** define `next_actions`.

- El LLM produce únicamente:
  - `decision` (qué quiso el usuario)
  - `policy` (cómo se puede responder)
- El Motor construye siempre:
  - `next_actions` de forma determinista (con fallbacks).

Esto reduce al mínimo el riesgo de:
- alucinaciones de acciones/keys
- cambios de contrato que rompen n8n
- acciones incompletas

---

## 3) Contrato v1 (congelado)

Endpoint:
- `POST /v1/motor/respond`

Requisito MVP:
- el output **siempre** cumple el mismo esquema (JSON estable)
- incluir `schema_version: "v1"` (o equivalente)

Enumeraciones cerradas:
- `policy.response_mode`: `TEMPLATE | FREEFORM`
- `next_actions[].type`: lista cerrada (ver sección 4)

Regla crítica:
- si falta algo o falla el LLM → **fallback determinista** (ver sección 5)

---

## 4) Taxonomía mínima de acciones (máximo 3)

En MVP, `next_actions` solo puede contener:

### A) SEND_MESSAGE (solo template)
Se usa cuando el canal requiere template o hay respuestas predefinidas.

Campos mínimos:
- `type: "SEND_MESSAGE"`
- `mode: "template"`
- `template_key`
- `vars` (siempre `{}`)
- `wa_id`
- `phone_number_id`

### B) DISPATCH_N8N (workflows/recetas)
Se usa cuando n8n debe hacer IA + búsquedas + enviar mensaje.

Campos mínimos:
- `type: "DISPATCH_N8N"`
- `workflow_key` (ej: `"WA_REPLY_V1"`)
- `input_json` (contexto suficiente para ejecutar)
- `wa_id`
- `phone_number_id`

Nota: `workflow_key` **NO** es el prompt de clasificación del Motor.  
Es el identificador del playbook/flow de n8n.

### C) HANDOFF
Se usa para derivar a humano o crear ticket.

Campos mínimos:
- `type: "HANDOFF"`
- `reason`
- `wa_id`
- `phone_number_id`
- (opcional) `queue`

Regla de simplificación MVP:
- `next_actions` debe ser **máximo 1 acción** en casos normales.
- Excepción safety: puede ser **2 acciones** (enviar template + handoff).

---

## 5) Mínimo ejecutable garantizado (fallbacks duros)

El sistema se considera MVP terminado cuando se cumplen estas garantías **siempre**, incluso si el LLM falla:

### Caso 1 — Ventana WhatsApp cerrada (>24h)
Siempre devuelve:
- `SEND_MESSAGE` template `REOPEN_24H`

### Caso 2 — Ventana abierta
Siempre devuelve:
- `DISPATCH_N8N` con `workflow_key="WA_REPLY_V1"`

### Caso 3 — Safety (lenguaje ofensivo / bloqueo)
Siempre devuelve:
- `SEND_MESSAGE` template `SAFE_BOUNDARY`
- `HANDOFF` (derivar)

Si el LLM falla o devuelve basura:
- no se rompe el flujo
- se aplica uno de estos fallbacks según corresponda

---

## 6) Templates: mapping real y seed mínimo

El MVP requiere que `template_key` signifique una sola cosa (fuente de verdad):
- o `Template.name` = `template_key`
- o un campo `Template.template_key` explícito (ideal)

Templates mínimos garantizados por tenant:
- `REOPEN_24H`
- `SAFE_BOUNDARY`
- `HANDOFF_GENERIC` (si se usa en derivaciones)

Regla MVP para evitar fallos por variables:
- `vars` siempre `{}` y/o templates diseñados sin variables obligatorias
  (o con defaults controlados)

---

## 7) Idempotencia / Dedup (resuelto como requisito)

El MVP se considera usable cuando:
- un retry del mismo `turn_wamid` **no genera efectos duplicados**
- y **no modifica memoria** si es duplicado

Regla:
- si el turno ya fue procesado → `next_actions: []`
- el orquestador debe interpretar eso como “NO OP” (no ejecutar nada)

---

## 8) Semántica de ejecución en n8n (MVP)

n8n ejecuta acciones del Motor así:

- `SEND_MESSAGE(template)` → enviar template a WhatsApp
- `DISPATCH_N8N(workflow_key=...)` → ejecutar flow:
  - generar texto (IA)
  - buscar inventario/eventos si aplica
  - enviar WhatsApp
  - (opcional) registrar outcome

Como `next_actions` es 1, evitamos problemas de orden/atomicidad.

---

## 9) Errores y reintentos (responsabilidad definida)

MVP requiere reglas claras:

- Si falla enviar WhatsApp:
  - n8n reintenta N veces con `dedupe_key` estable  
    ejemplo: `tenant::turn_wamid::send`
- Si falla una consulta (inventario):
  - n8n aplica fallback (mensaje estándar) y/o dispara `HANDOFF`

---

## 10) Memoria (summary + facts_json) en MVP

Objetivo:
- mejorar coherencia, evitar repetir preguntas

Reglas MVP:
- duplicados no actualizan memoria
- `facts_json` = datos estructurados (campos concretos)
- `summary` = resumen corto del estado del lead
- no se busca perfección; solo consistencia mínima

---

## 11) Observabilidad mínima (obligatoria)

Cada respuesta debe permitir debug rápido:

Debe incluir:
- `trace_id` (o usar `tenant_id + turn_wamid` como correlación)
- `telemetry` mínimo:
  - `window_open`
  - `llm_used`
  - `llm_fallback`
  - `duplicate_turn`

n8n debe loguear outcome con el mismo `trace_id`.

---

## 12) Versionado Motor ↔ n8n

MVP requiere:
- `schema_version: "v1"` en la respuesta del Motor
- n8n valida versión:
  - si no coincide → “dead letter / alerta”
  - no ejecutar acciones a ciegas

---

## 13) Prueba final (E2E) para declarar MVP terminado

El MVP se declara terminado cuando pasan estos casos end-to-end:

1) Ventana abierta → Motor devuelve `DISPATCH_N8N` → n8n responde y envía WhatsApp  
2) Ventana cerrada → Motor devuelve template `REOPEN_24H` → n8n envía template  
3) Safety → Motor devuelve `SAFE_BOUNDARY` + `HANDOFF` → n8n envía y deriva  
4) Retry mismo `turn_wamid` → Motor devuelve `next_actions: []` → n8n NO envía nada  
5) Falla lookup inventario → n8n fallback + (opcional) handoff (según regla)

---

## Resultado esperado

Cuando todo esto está cumplido:
- el sistema es **usable** (no se rompe, no duplica, no queda en limbo)
- n8n ejecuta flujos sin adivinar el contrato
- el Motor queda como “cerebro de decisión” estable
- podemos iterar a producto mejorado sin reescribir la bases