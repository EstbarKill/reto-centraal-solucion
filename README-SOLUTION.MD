# Reto Centraal — Sistema Serverless de Mantenimiento Predictivo

## Descripción

Solución serverless desarrollada en Python sobre Azure Functions para procesamiento de eventos industriales y generación de predicciones de riesgo de falla en maquinaria.

El sistema recibe eventos de sensores en tiempo real, los procesa de manera asíncrona mediante Azure Queue Storage, los persiste en Azure Blob Storage usando archivos NDJSON particionados y expone APIs REST para cálculo de predicciones por máquina.

---

# Objetivos del proyecto

- Construir una arquitectura desacoplada y escalable.
- Procesar eventos industriales de forma asíncrona.
- Persistir telemetría histórica eficientemente.
- Generar predicciones de riesgo explicables.
- Implementar validación e idempotencia.
- Simular un flujo cercano a producción cloud-native.

---

# Arquitectura

```text
                +----------------------+
                | PUT /api/sensors     |
                +----------+-----------+
                           |
                           v
                +----------------------+
                | Azure Queue Storage  |
                +----------+-----------+
                           |
                           v
                +----------------------+
                | Queue Trigger Worker |
                +----------+-----------+
                           |
                           v
                +----------------------+
                | Azure Blob Storage   |
                | NDJSON particionado  |
                +----------+-----------+
                           |
                           v
                +----------------------+
                | Prediction Engine    |
                +----------+-----------+
                           |
            +--------------+---------------+
            |                              |
            v                              v
+------------------------+   +-------------------------+
| GET /prediction/{id}   |   | GET /predictions        |
+------------------------+   +-------------------------+
```

---
# Tecnologías utilizadas

## Backend
- Python 3.11
- Azure Functions v2
- Azure Queue Storage
- Azure Blob Storage
- Azurite

## Persistencia
- NDJSON (Newline Delimited JSON)

## Herramientas
- Azure Functions Core Tools
- Insomnia / PowerShell
- pandas
- requests
---

---
# Características técnicas implementadas

- Arquitectura serverless
- Procesamiento asíncrono
- Event-driven pipeline
- Persistencia particionada
- NDJSON incremental
- Idempotencia
- Deduplicación de eventos
- Logging estructurado
- Predicciones explicables
- APIs REST
- Validación de payloads
- Simulación masiva de sensores
---

---
## Estructura del proyecto

```text
.
├── function_app.py
├── simulate.py
├── clear_queues.py
├── requirements.txt
├── host.json
├── local.settings.json
├── notebook/
│   ├── sensor_data_april_2026.csv
│   └── sensor_data_may_2026.csv
├── src/
│   ├── function.json
│   ├── ingestion.py
│   ├── prediction.py
│   ├── queue_worker.py
│   ├── storage.py
│   ├── validation.py
│   └── models.py
└── test/
```
---

---
# Flujo del sistema

## Ingesta de sensores
PUT /api/sensors
 - machine_id
 - timestamp
 - variable
 - value

## Procesamiento asíncrono
queue_worker
 - Consumir mensajes
 - Validar payload
 - Persistir eventos en Blob Storage

## Persistencia
Almacenamiento en NDJSON
```text
    machine_id=PUMP-1001/
        year=2026/
            month=05/
            day=07/
                events.ndjson
```
Formato:

```json
{"machine_id":"PUMP-1001","timestamp":"2026-05-07T03:00:00Z","variable":"temperature_c","value":71.8}
```
## Deduplicación e idempotencia
    - SHA256 hash
    - event_id -> Generate - machine_id + timestamp + variable + value
    - Validación previa a persistencia


## APIs
PUT /api/sensors -> Recibe eventos de sensores.

    Ejemplo
```json
        {
            "machine_id": "PUMP-1001",
            "timestamp": "2026-05-07T03:00:00Z",
            "variable": "temperature_c",
            "value": 71.8
        }
```
    Respuesta 
```json
        {
            "status": "ok",
            "machine_id": "PUMP-1001"
        }
```

GET /api/machines/{machine_id}/prediction -> Obtiene predicción individual.

    Ejemplo
    /api/machines/PUMP-1001/prediction

    Respuesta
        {
            "machine_id": "PUMP-1001",
            "failure_probability_24h": 0.316,
            "risk_factors": [
                "temperature_c: máximo 71.98 supera umbral nominal 70.00"
            ],
            "window_hours": 24,
            "events_considered": 29
        }
GET /api/predictions

Respuesta:

```json
{
    "machines_scanned": 10,
    "predictions": [
        {
            "machine_id": "PUMP-1001",
            "failure_probability_24h": 0.316
        }
    ]
}
```
---

---
# Motor de prediccion
    - Agregaciones estadísticas
    - Umbrales nominales
    - Score ponderado
    - Función sigmoide

## Variables soportadas
    - vibration_mm_s
    - temperature_c
    - current_a
    - pressure_bar
    - load_pct
---

---
# Cómo ejecutar
    - Clonar repositorio
        git clone https://github.com/EstbarKill/reto-centraal-solucion.git
    - Crear entorno virtual
        python -m venv .venv
    - Activar
        .venv\\Scripts\\activate
    - Instalar dependencias
        pip install -r requirements.txt
    - Iniciar azurite 

        ```bash
        azurite --skipApiVersionCheck
        ```
        El parámetro `--skipApiVersionCheck` evita incompatibilidades entre versiones recientes de Azurite y el SDK de Azure utilizado por Python.
    - Ejecutar Azure Functions
        func start
    - Ejecutar simulación
        python simulate.py
    - Simulación
        El script simulate.py carga "sensor_data_april_2026.csv"
        Realiza evento "PUT /api/sensors"
---

---
# Bug encontrado y solución
## Problema
    Durante el desarrollo el pipeline asíncrono no persistía correctamente los eventos.
## Síntomas
    - blobs vacíos
    - predicciones sin eventos
    - events_considered = 0
    - mensajes inconsistentes en Queue Storage
## Causa raíz
Incompatibilidad de encoding entre:
    - Azure Queue Storage
    - Azure Functions Queue Trigger
    - serialización del mensaje.
## Solución aplicada
Ajustes:
        - manejo de msg.get_body(),
        - decodificación UTF-8,
        - serialización JSON,
        - logging completo,
        - validación del pipeline.
## Evidencia funcional
Ingesta exitosa
    PUT /api/sensors

Resultado:
{
  "status": "ok",
  "machine_id": "PUMP-1001"
}

## Persistencia correcta
Blob generado:
    machine_id=PUMP-1001/year=2026/month=05/day=07/events.ndjson
## Predicción individual
Respuesta 
    {
        "machine_id": "PUMP-1001",
        "failure_probability_24h": 0.316,
        "events_considered": 29
    }
## Predicción global
Respuesta
    {
        "machines_scanned": 10
    }

---
---

# Pruebas unitarias

El proyecto incluye pruebas unitarias para validar los componentes críticos del pipeline serverless.

## Cobertura actual

- Validación de payloads
- Generación de `event_id`
- Serialización NDJSON
- Construcción de rutas Blob Storage
- Cálculo de features estadísticas
- Evaluación de riesgo y score
- Validación de endpoints de ingesta

## Estructura de pruebas

```text
tests/
├── test_ingestion.py
├── test_models.py
├── test_prediction.py
├── test_storage.py
└── test_validation.py
```

## Ejecutar pruebas

Instalar dependencias:

```bash
pip install -r requirements-dev.txt
```

Ejecutar tests:

```bash
pytest -v
```

Ejecutar cobertura:

```bash
pytest --cov=src tests/
```

## Resultado esperado

```text
11 passed
```

---

# Calidad de ingeniería aplicada

- Arquitectura desacoplada
- Event-driven architecture
- Validación defensiva
- Idempotencia
- Logging estructurado
- Persistencia particionada
- Testing automatizado
- Separación de responsabilidades
- Diseño cloud-native

---

---
# Posibles mejoras
- Entrenamiento ML real.
- Modelos supervisados.
- Azure Event Hub / Kafka.
- Persistencia incremental.
- Dashboard en tiempo real.
- Alertas automáticas.
- Anomaly Detection.
- Time Series Forecasting.
- Feature Engineering avanzado.

# Principios aplicados 
- Arquitectura desacoplada
- Event-driven architecture
- Idempotencia
- Separación de responsabilidades
- Logging estructurado
- Validación defensiva
- Diseño cloud-native
---

---
# Autor
Desarrollado por:

    Ingeniero Estevan Alejandro Cabarcas Urieles

---
