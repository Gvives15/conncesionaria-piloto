# Especificaciones de Mejora para Motor de Respuesta (v2.1)

## 1. Resumen Ejecutivo
Tras el análisis de rendimiento y pruebas de estrés del módulo `motor_response`, se han identificado áreas críticas que afectan la estabilidad y observabilidad del sistema. Este documento detalla las correcciones obligatorias y mejoras recomendadas para la siguiente iteración.

## 2. Hallazgos Críticos (Bugs & Estabilidad)

### 2.1. IntegrityError en `MemoryRecord`
**Severidad:** ALTA
**Descripción:** El sistema falla con un error 500 cuando el LLM no devuelve el campo `secondary_events` o devuelve `null`. La base de datos (SQLite/Postgres) tiene una restricción `NOT NULL` en la columna `active_secondary_events`, pero el código en `api.py` permite pasar `None` al modelo.

**Evidencia (Log de Test):**
```text
django.db.utils.IntegrityError: NOT NULL constraint failed: whatsapp_inbound_memoryrecord.active_secondary_events
File "motor_response\api.py", line 382, in motor_respond
    mem_obj.save(...)
```

**Solución Requerida:**
Modificar `motor_response/api.py` para garantizar que siempre se asigne una lista vacía `[]` si el valor es `None`.

```python
# Antes
mem_obj.active_secondary_events = memory_update.get("active_secondary_events") or secondary_events

# Después (Propuesto)
mem_obj.active_secondary_events = (memory_update.get("active_secondary_events") or secondary_events) or []
```

### 2.2. Manejo Silencioso de Errores de LLM
**Severidad:** MEDIA
**Descripción:** Cuando `classify_with_openai` falla (por timeout, auth, o error 500 de OpenAI), el sistema captura el error y devuelve un evento `FALLBACK`. Sin embargo, el error real queda enterrado en el campo `telemetry` o logs internos, dificultando el diagnóstico en producción sin inspeccionar el payload completo.

**Solución Requerida:**
1. Loggear el error exacto con nivel `ERROR` en `django.request`.
2. Incluir un flag `warning` en la respuesta de nivel superior si se activó el modo Fallback por error técnico.

## 3. Mejoras de Rendimiento (Performance)

### 3.1. Métricas Actuales
*   **Latencia Interna (sin LLM):** ~1.7ms (P99 < 3ms).
*   **Throughput:** ~580 req/s (en entorno de prueba local).
*   **Cuello de Botella:** I/O de Base de Datos (lectura de Tenant/Eventos en cada request).

### 3.2. Optimización de Lectura de Configuración
Actualmente, cada petición a `/v1/motor/respond` ejecuta:
1. `SELECT` a `Tenant`.
2. `SELECT` a `Contact`.
3. `SELECT` a `MemoryRecord`.
4. `SELECT` a `TenantEvent` (lista completa).
5. `SELECT` a `Template` (lista completa).

**Recomendación:**
Implementar caché en memoria (ej. `django-cache` con Redis o `lru_cache` local con TTL corto) para:
*   `_load_tenant_events(tenant_id)`
*   `_load_available_templates(tenant_id)`

Esto reducirá 2 consultas por request, mejorando la latencia base y reduciendo la carga en la DB.

## 4. Estandarización de Tests
**Observación:** La estructura de tests actual es fragmentada (`tests/` vs raíz) y depende de configuraciones manuales de `PYTHONPATH`.
**Acción:** Mover todos los scripts de prueba (`test_motor_full.py`, etc.) a la estructura estándar de `tests/` y asegurar que funcionen con `pytest` sin intervención manual.

## 5. Plan de Implementación
1. **Inmediato:** Hotfix para `IntegrityError` (2.1).
2. **Corto Plazo:** Implementación de logs estructurados para errores de LLM (2.2).
3. **Mediano Plazo:** Caché de eventos y templates (3.2).
