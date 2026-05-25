import os
from dotenv import load_dotenv
from pymongo import MongoClient
from neo4j import GraphDatabase
import redis

# Cargamos las variables del archivo .env
load_dotenv()

# 1. Conexión MongoDB (Ya tiene timeout de 2000ms)
try:
    mongo_client = MongoClient(os.getenv("MONGO_URI"), serverSelectionTimeoutMS=2000)
    db_mongo = mongo_client["sistema_hospitalario"]
    mongo_client.server_info()
    print("✅ MongoDB: Conectado")
except Exception:
    print("❌ MongoDB: DOWN")
    db_mongo = None

# 2. Conexión Neo4j (Le agregamos connection_timeout)
try:
    neo4j_driver = GraphDatabase.driver(
        os.getenv("NEO4J_URI"), 
        auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD")),
        connection_timeout=2.0  # <--- Clave: corta a los 2 segundos si no conecta
    )
    neo4j_driver.verify_connectivity()
    print("✅ Neo4j: Conectado")
except Exception:
    print("❌ Neo4j: DOWN")
    neo4j_driver = None

# 3. Conexión Redis (Le agregamos socket_timeout)
try:
    db_redis = redis.Redis(
        host=os.getenv("REDIS_HOST"), 
        port=int(os.getenv("REDIS_PORT")), 
        decode_responses=True,
        socket_timeout=2.0  # <--- Clave: corta a los 2 segundos si no responde
    )
    db_redis.ping()
    print("✅ Redis: Conectado")
except Exception:
    print("❌ Redis: DOWN")
    db_redis = None