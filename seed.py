import os
import json
from config.database import db_mongo, db_redis

# Colecciones a procesar desde archivos en seeds/
COLECCIONES = ("hospitales", "medicos", "pacientes", "consultas", "turnos")

DIR_SEEDS = os.path.join(os.path.dirname(__file__), "seeds")


def seed_mongodb():
    print("\n📦  MongoDB: Carga de datos históricos")
    for coleccion in COLECCIONES:
        archivo = os.path.join(DIR_SEEDS, f"{coleccion}.json")

        if db_mongo[coleccion].count_documents({}) > 0:
            print(f"   ⚠️  Colección '{coleccion}' ya contiene datos. Saltando carga histórica para evitar duplicados.")
            continue

        if not os.path.isfile(archivo):
            print(f"   ⚠️  Archivo '{archivo}' no encontrado. Saltando.")
            continue

        with open(archivo, "r", encoding="utf-8") as f:
            documentos = json.load(f)

        db_mongo[coleccion].insert_many(documentos)
        print(f"   ✅  Colección '{coleccion}' — {len(documentos)} documentos insertados.")


def seed_redis():
    print("\n⚡  Redis: Sincronización de estado operativo")

    db_redis.flushdb()
    print("   🧹  Redis limpiado (flushdb).")

    # --- Camas por hospital ---
    hospitales = list(db_mongo["hospitales"].find({}))
    for hosp in hospitales:
        hid = hosp["_id"]
        for nro in range(1, 6):
            key = f"cama:{hid}:{nro}"
            db_redis.hset(key, mapping={
                "hospital": hid,
                "sector": "General",
                "numero": str(nro),
                "estado": "disponible",
            })
    print(f"   🛏️   {len(hospitales) * 5} camas creadas ({len(hospitales)} hospitales × 5).")

    # --- Médicos por especialidad ---
    medicos = list(db_mongo["medicos"].find({}))
    for med in medicos:
        esp = med.get("especialidad")
        if not esp:
            continue
        miembro = med.get("matricula") or med["_id"]
        db_redis.sadd(f"medicos:{esp}", miembro)
    print(f"   👨‍⚕️  {len(medicos)} médicos indexados por especialidad.")


# TO DO: seed_neo4j()

def run():
    print("🚀 Iniciando proceso de seeding políglota...")

    if db_mongo is None:
        print("❌ MongoDB no está disponible. Abortando seeding.")
        return

    seed_mongodb()

    if db_redis is None:
        print("❌ Redis no está disponible. Se salta la sincronización operativa.")
        return

    seed_redis()

    print("\n✅ Seeding completado exitosamente.\n")


if __name__ == "__main__":
    run()
