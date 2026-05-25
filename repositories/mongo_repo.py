from datetime import datetime, timezone
from config.database import db_mongo

def _get_db():
    if db_mongo is None:
        raise ConnectionError("MongoDB no está disponible. Verifique que el contenedor esté corriendo.")
    return db_mongo


def registrar_internacion_historica(paciente_id, hospital_id, medico_id, sector, numero_cama):
    try:
        db = _get_db()

        internacion = {
            "paciente_id": paciente_id,
            "hospital_id": hospital_id,
            "medico_id": medico_id,
            "sector": sector,
            "numero_cama": numero_cama,
            "fecha": datetime.now(timezone.utc),
            "tipo": "internacion"
        }

        db.internaciones_historicas.insert_one(internacion.copy())

        db.consultas.update_one(
            {"paciente_id": paciente_id},
            {
                "$push": {
                    "historial": {
                        "tipo": "internacion",
                        "hospital_id": hospital_id,
                        "medico_id": medico_id,
                        "sector": sector,
                        "numero_cama": numero_cama,
                        "fecha": datetime.now(timezone.utc),
                    }
                }
            },
            upsert=True
        )

        return {"mensaje": "Internación registrada correctamente", "paciente_id": paciente_id}
    except ConnectionError:
        raise
    except Exception as e:
        raise RuntimeError(f"Error al registrar internación histórica: {str(e)}") from e


def registrar_derivacion_historica(paciente_id, medico_derivante_id, especialidad_destino, hospital_destino_id, motivo):
    try:
        db = _get_db()

        derivacion = {
            "paciente_id": paciente_id,
            "medico_derivante_id": medico_derivante_id,
            "especialidad_destino": especialidad_destino,
            "hospital_destino_id": hospital_destino_id,
            "motivo": motivo,
            "fecha": datetime.now(timezone.utc),
            "estado": "pendiente"
        }

        db.derivaciones.insert_one(derivacion)

        return {"mensaje": "Derivación registrada correctamente", "paciente_id": paciente_id}
    except ConnectionError:
        raise
    except Exception as e:
        raise RuntimeError(f"Error al registrar derivación histórica: {str(e)}") from e


def obtener_ultimas_consultas(paciente_id, limite=5):
    try:
        db = _get_db()

        cursor = db.consultas.find(
            {"paciente_id": paciente_id}
        ).sort([("fecha", -1)]).limit(limite)

        resultado = list(cursor)
        for doc in resultado:
            doc["_id"] = str(doc["_id"])

        return resultado
    except ConnectionError:
        raise
    except Exception as e:
        raise RuntimeError(f"Error al obtener últimas consultas: {str(e)}") from e


def obtener_prescripciones_activas(paciente_id):
    try:
        db = _get_db()

        pipeline = [
            {"$match": {"paciente_id": paciente_id}},
            {"$unwind": "$prescripciones"},
            {
                "$addFields": {
                    "fecha_fin": {
                        "$dateAdd": {
                            "startDate": "$prescripciones.fecha",
                            "unit": "day",
                            "amount": "$prescripciones.duracion_dias"
                        }
                    }
                }
            },
            {
                "$match": {
                    "fecha_fin": {"$gte": datetime.now(timezone.utc)}
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "paciente_id": 1,
                    "medicamento": "$prescripciones.medicamento",
                    "dosis": "$prescripciones.dosis",
                    "frecuencia": "$prescripciones.frecuencia",
                    "fecha_inicio": "$prescripciones.fecha",
                    "fecha_fin": 1,
                    "duracion_dias": "$prescripciones.duracion_dias"
                }
            }
        ]

        resultado = list(db.consultas.aggregate(pipeline))
        return resultado
    except ConnectionError:
        raise
    except Exception as e:
        raise RuntimeError(f"Error al obtener prescripciones activas: {str(e)}") from e
