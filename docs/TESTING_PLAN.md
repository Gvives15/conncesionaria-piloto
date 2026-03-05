# Plan de Pruebas del Motor de Respuestas (Response Engine)

Este documento define la estrategia de pruebas para validar el funcionamiento correcto, robusto y seguro del Motor de Respuestas del sistema.

## 1. Objetivos
- Validar que el motor clasifique correctamente las intenciones del usuario.
- Asegurar que el contexto de la conversación se mantenga y actualice correctamente.
- Verificar el comportamiento ante ventanas de conversación cerradas (24hs).
- Garantizar la seguridad y estabilidad ante entradas maliciosas o inesperadas.
- Medir el rendimiento bajo carga.

## 2. Alcance
El plan cubre el endpoint principal `/v1/motor/respond` y sus componentes internos:
- `motor_response.api.motor_respond`
- `motor_response.llm_classifier`
- Interacción con la base de datos (Modelos: `Tenant`, `Contact`, `MemoryRecord`, `TenantEvent`, `Template`).

## 3. Tipos de Pruebas

### 3.1. Pruebas Funcionales (Unitarias e Integración)
Se ejecutarán con `pytest` y `pytest-django`.

**Casos de Prueba:**
1.  **Flujo Básico (Happy Path)**:
    - Entrada: Texto usuario normal.
    - Condición: Ventana abierta, eventos configurados.
    - Resultado esperado: `primary_event` detectado, `policy=FREEFORM`, `memory_update` correcto.
2.  **Ventana Cerrada (>24hs)**:
    - Entrada: Cualquier texto.
    - Condición: `last_user_message_at` > 24hs.
    - Resultado esperado: `policy=TEMPLATE`, `next_actions` contiene `SEND_MESSAGE` con template.
3.  **Filtro de Seguridad (Profanity)**:
    - Entrada: Texto con palabras ofensivas.
    - Resultado esperado: `primary_event=SAFETY_BLOCK`, `block=True`.
4.  **Sin Eventos Configurados (Fallback)**:
    - Entrada: Texto normal.
    - Condición: Tenant sin eventos.
    - Resultado esperado: `primary_event=FALLBACK`, `policy=FREEFORM` (si ventana abierta).
5.  **Persistencia de Memoria**:
    - Verificar que `summary`, `recent_events` y `facts_json` se guarden en DB tras la respuesta.

### 3.2. Pruebas de Borde (Edge Cases)
1.  **Entradas Vacías o Nulas**: `text=""`, `text=None`.
2.  **Strings Largos**: Payload de texto > 10KB.
3.  **Caracteres Especiales**: Emojis, alfabetos no latinos, inyecciones SQL simuladas.
4.  **Tenant Inexistente**: `tenant_id` random.

### 3.3. Pruebas de Integración (Mocked LLM)
- Simular respuestas del LLM (OpenAI) para validar que el sistema procesa correctamente el JSON de salida, incluyendo casos de error o JSON malformado.

### 3.4. Pruebas de Rendimiento (Load Testing)
- Script de `locust` o `pytest-benchmark` para medir latencia promedio y throughput.
- **Meta**: Tiempo de respuesta < 2s (incluyendo latencia LLM simulada) o < 5s (con LLM real).

### 3.5. Pruebas de Seguridad
- Validación de inputs para evitar inyecciones.
- Verificación de aislamiento de datos entre Tenants (un tenant no debe acceder a eventos de otro).

## 4. Herramientas
- **Framework**: `pytest`, `pytest-django`
- **Mocking**: `unittest.mock`
- **Runner**: `make test` o script CI/CD.

## 5. Criterios de Éxito
- 100% de los tests funcionales y de borde pasan.
- Cobertura de código (Code Coverage) > 80% en el módulo `motor_response`.
- Latencia p95 < 5s.

---

## 6. Ejecución
Para ejecutar las pruebas:
```bash
pytest
```
