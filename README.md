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
```bash