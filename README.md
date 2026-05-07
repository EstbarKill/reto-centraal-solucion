# 🚀 Mantenimiento Predictivo Central: Arquitectura sin Servidor basada en Eventos (Azure)

## 🧭 Resumen Ejecutivo

Este proyecto implementa un **sistema de mantenimiento predictivo sin servidor y nativo de la nube** diseñado para cargas de trabajo de IoT industrial.

Ingiere telemetría de sensores de alta frecuencia, la procesa de forma asíncrona, la almacena en un lago de datos y calcula predicciones de riesgo de fallas casi en tiempo real mediante un motor de puntuación estadística ligero.

La arquitectura está optimizada para:

- Alto rendimiento de ingesta
- Tolerancia a fallos
- Escalabilidad basada en eventos
- Eficiencia de costes (diseño sin servidor)

---

# 🏗️ Arquitectura de alto nivel

```

┌──────────────────────┐

│ IoT / Clientes │

└─────────┬───────────┘

│ HTTP

▼
┌──────────────────────────┐

│ Azure Functions (API) │

│ ingestion.py │

└─────────┬────────────────┘

│ validar + encolar

▼
┌──────────────────────────┐

│ Almacenamiento de colas de Azure │

│ Cola de eventos de sensores │

└─────────┬────────────────┘

│ Disparador asíncrono

▼
┌──────────────────────────┐

│ Trabajador de Azure Functions │

│ queue_worker.py │

└─────────┬───────────────┘

│ Eventos de solo adición

▼
┌──────────────────────────┐

│ Azure Blob Storage │

│ NDJSON Data Lake │

└─────────┬───────────────┘

│ lecturas por lotes

▼
┌──────────────────────────┐

│ Capa de características + puntuación │

│ prediction.py │

└─────────┬───────────────┘

│
┌─────────────┴─────────────┐

▼ ▼
GET /prediction/{id} GET /predictions
```

---

# 🧱 Principios de diseño principales
## 1. Arquitectura basada en eventos
La ingesta de sensores se desacopla mediante mensajería basada en colas para garantizar:

- Gestión de la contrapresión
- Resiliencia ante picos de tráfico
- Escalado independiente de los componentes

---
## 2. Diseño sin servidor
Azure Functions se utiliza para:

- Capa de ingesta de API
- Procesamiento en segundo plano
- Puntos de conexión de predicción
Esto garantiza:

- Escalado automático
- Modelo de coste de pago por ejecución
- Gestión de infraestructura cero

---

## 3. Data Lake de solo anexión (NDJSON)

Los eventos se almacenan en:

```
machine_id=<id>/year=AAAA/month=MM/day=DD/events.ndjson
```

Ventajas:

- Registro de auditoría inmutable
- Capacidad de reproducción
- Formato optimizado para análisis
- Modelo de almacenamiento de bajo coste

---

## 4. Idempotencia y deduplicación

A cada evento se le asigna:

```
event_id = SHA256(machine_id + marca de tiempo + variable + valor)
```

Se utiliza para:

- Evitar la ingesta duplicada
- Garantizar la coherencia en el procesamiento distribuido

---

# 📊 Flujo de datos

```
Evento del sensor

↓
API HTTP (Capa de validación)
↓
Cola (Búfer / Desacoplamiento)

↓
Proceso de trabajo (Normalización + Persistencia)

↓
Almacenamiento de blobs (Conjunto de datos histórico)

↓
Ingeniería de características (Agregación)

↓
Motor de puntuación de riesgo

↓
Salida de probabilidad (0–1)
```

---

# ⚙️ Motor de predicción

## Extracción de características

Para cada variable del sensor:

- Último valor observado
- Valor medio (ventana de 24 h)
- Valor máximo (ventana de 24 h)

## Modelo de puntuación

```
Puntuación = Σ (exceso sobre el umbral)
```

Donde:

- Los umbrales representan los rangos operativos nominales
- Las desviaciones se ponderan según la gravedad

## Transformación

Probabilidad final:

```
P(fallo) = sigmoide(α * (puntuación - sesgo))
```

---

# 🌐 Superficie de la API

## API de ingesta

`PUT /api/sensors`

Acepta:

```json
{
"machine_id": "PUMP-1001",

"timestamp": "2026-05-07T03:00:00Z",

"variable": "temperature_c",

"value": 71.8
}
```

---

## Predicción de máquina

`GET /api/machines/{id}/prediction`

Devuelve:

```json
{
"machine_id": "PUMP-1001",

"failure_probability_24h": 0.316,

"risk_factors": [
"temperature_c exceeds nominal threshold"

],
"eventos_considerados": 29
}
```

---

## Predicciones globales

`GET /api/predictions`

---

# 🧪 Fiabilidad y observabilidad

## Estrategia de registro

- Registros estructurados por módulo
- Correlación por flujo de eventos
- Trazabilidad completa desde la ingesta hasta el almacenamiento y la predicción

## Gestión de fallos

- Mecanismo de reintento de cola (Azure Queue)
- Propagación de excepciones del trabajador
- Reprocesamiento seguro de eventos

## Compromisos conocidos

| Área | Compromiso |

|------|----------|

| Almacenamiento | Amplificación de lectura (escaneo completo de blobs) |

| Deduplicación | Verificación en memoria (no distribuida) |

| Modelo de aprendizaje automático | Heurística (no entrenada) |

---

# 🚀 Consideraciones de escalabilidad

El diseño actual admite:

- Escalado horizontal de funciones
- Almacenamiento particionado por máquina/fecha
- Almacenamiento en búfer de cola asíncrona

Posibles actualizaciones:

- Azure Event Hub (ingesta de alto rendimiento)
- Cosmos DB (deduplicación + indexación)
- Stream p