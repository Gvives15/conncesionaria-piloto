# Tests E2E Motor Live (OpenAI Real)

Este suite de tests ejecuta el endpoint `POST /v1/motor/respond` contra el entorno real.

## Estructura Multi-Tenant

Los tests están organizados por "cliente" o configuración de negocio para permitir escalar a múltiples empresas.

- `tests/e2e_motor_live/`: Raíz de tests E2E Live.
  - `e2e_distribuidora/`: Suite específica para "Distribuidora Test".
    - `conftest.py`: Fixtures de Tenant, Catálogo y Templates de Distribuidora.
    - `data/cases.jsonl`: Casos de prueba específicos.
    - `test_*.py`: Tests ejecutables.

## Requisitos

Variables de entorno necesarias:
```bash
export OPENAI_API_KEY="sk-..."
export LLM_CLASSIFIER_PROMPT_ID="asst_..."
```

## Ejecución (Distribuidora)

Para correr los tests de la distribuidora:

### 1. Test de Reglas Básicas
```bash
pytest -q -m "llm_live" tests/e2e_motor_live/e2e_distribuidora/test_01_rules_live.py
```

### 2. Test de Deduplicación
```bash
pytest -q -m "llm_live" tests/e2e_motor_live/e2e_distribuidora/test_02_dedupe_live.py
```

### 3. Test Golden (Casos Masivos)
```bash
pytest -q -m "llm_live" tests/e2e_motor_live/e2e_distribuidora/test_03_golden_live.py
```

### Ejecutar Todo el Suite Distribuidora
```bash
pytest -m "llm_live" tests/e2e_motor_live/e2e_distribuidora/
```

## Reportes

Cada ejecución genera/anexa resultados en formato JSONL en:

`artifacts/motor_live_results.jsonl`
