# Sistema de Gestión para Red de Hospitales Públicos - Segunda Entrega

Este proyecto implementa una capa de persistencia políglota utilizando **MongoDB** (historial clínico y turnos), **Neo4j** (red de derivaciones y contraindicaciones) y **Redis** (gestión operativa en tiempo real) coordinados mediante una API REST en **Python con FastAPI**.

---

## 🚀 Requisitos Previos

Antes de levantar la aplicación, asegurate de tener instalado en tu máquina:
* **Docker Desktop** (con soporte para WSL 2 en Windows)
* **Python 3.10 o superior**
* **MongoDB Compass** (opcional, para visualización de datos)

---

## 🛠️ Paso 1: Levantar los Motores de Base de Datos (Docker)

Para no instalar cada motor de forma nativa, utilizamos Docker Compose. Desde la terminal, en la raíz del proyecto, ejecutá:


docker-compose up -d

## 🐍 Paso 2: Configuración del Entorno de Python
Configurar el archivo de entorno:

Verificá que el archivo .env esté en la raíz del proyecto con las siguientes variables de conexión:

MONGO_URI=mongodb://localhost:27017/
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password123
REDIS_HOST=localhost
REDIS_PORT=6379

Instalar las dependencias del proyecto:
Ejecutá el siguiente comando para instalar los drivers oficiales NoSQL y el framework de la API:  

pip install -r requirements.txt

## 💾 Paso 3: Carga Inicial de Datos (Seeding Políglota)

El proyecto cuenta con un script automatizado para poblar las bases de datos y garantizar que todos los integrantes del equipo trabajemos con los mismos datos de prueba e identificadores (IDs).

Para ejecutarlo, corré el siguiente comando en tu terminal:

python seed.py

## Paso 4: Ejecutar la Aplicación Backend##
Para levantar el servidor de desarrollo con recarga automática ante cambios de código, ejecutá:

python -m uvicorn main:app --reload

La API se levantará en: http://localhost:8000

Para ver el swagger y ejecutar los endpoints entrar a: http://localhost:8000/docs


## 🏗️ Arquitectura del Sistema y Flujo Políglota

El backend está desarrollado sobre **FastAPI** utilizando una **arquitectura en capas (Patrón Repositorio)**, aislando por completo la lógica de acceso a datos de los endpoints de la API.

### 📁 Componentes Clave del Proyecto

* **`config/database.py` (Capa de Conexión):** Se encarga del ciclo de vida de las conexiones. Centraliza la lectura de variables de entorno y expone las instancias globales `db_mongo`, `neo4j_driver` y `db_redis`. Cuenta con *Health Checks* y *timeouts* estrictos de 2 segundos para garantizar la tolerancia a fallos si un contenedor se cae.
* **`repositories/` (Capa de Persistencia Aislada):** Cada motor NoSQL tiene su propio archivo e interfaz, permitiendo un desarrollo desacoplado y en paralelo:
    * `mongo_repo.py`: Almacena documentos extensos y complejos (historial clínico y agregaciones analíticas de ocupación de los últimos 30 días).
    * `redis_repo.py`: Gestiona estructuras de alta velocidad y tiempo real (Hashes para estado de camas, Sorted Sets para colas de prioridad de guardias y Streams para el log de eventos críticos).
    * `neo4j_repo.py`: Resuelve consultas de relaciones complejas mediante Cypher (grafo de incompatibilidades de medicamentos y redes de derivación).
* **`main.py` (Capa de Orquestación y Rutas):** Recibe las peticiones HTTP, extrae los parámetros y coordina los llamados a los distintos repositorios. Es el encargado de ensamblar las respuestas políglotas unificadas y de ejecutar las **transacciones compensatorias** ante fallos parciales para mantener la consistencia entre los motores.

```bash