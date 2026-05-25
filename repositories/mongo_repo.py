from datetime import datetime, timezone
from config.database import db_mongo

def _get_db():
    if db_mongo is None:
        raise ConnectionError("MongoDB no está disponible. Verifique que el contenedor esté corriendo.")
    return db_mongo


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


def obtener_historial_y_prescripciones(paciente_id: str) -> dict:
    """
    [OP-1] Obtiene el historial clínico completo del paciente en una sola consulta.

    Debe ejecutar un pipeline de agregación sobre la colección 'consultas' que:
      1. Filtre por paciente_id.
      2. Use $facet para ejecutar dos ramas en paralelo:
         - 'ultimas_consultas': $sort por fecha descendente, $limit 5.
         - 'prescripciones_activas': $unwind sobre el array 'prescripciones',
            calcular fecha_fin ($dateAdd con duracion_dias), $match con fecha_fin >= ahora.
      3. Retornar un dict con las claves 'ultimas_consultas' y 'prescripciones_activas'.

    Llamar a _get_db() al inicio y manejar ConnectionError / Exception.
    """
    raise NotImplementedError()


def registrar_turno_urgencia(paciente_id: str, medico_id: str, especialidad: str) -> dict:
    """
    [OP-2] Inserta un nuevo turno de urgencia en el historial del paciente.

    Construir un documento con:
      - paciente_id, medico_id, especialidad
      - tipo: "urgencia"
      - fecha: datetime.now(timezone.utc)

    Insertarlo en la colección 'consultas' usando insert_one.
    Si la colección ya usa un array historial, hacer $push dentro de un update_one con upsert.

    Llamar a _get_db() al inicio. Retornar {"mensaje": "...", "paciente_id": paciente_id}.
    """
    raise NotImplementedError()


def obtener_ocupacion_historica(hospital_id: str) -> list:
    """
    [OP-3] Calcula el promedio diario de ocupación por sector en los últimos 30 días.

    Pipeline de agregación sobre la colección 'internaciones_historicas':
      1. $match: hospital_id y fecha >= (hoy - 30 días).
      2. $group por sector y por día ($dateToString con formato "%Y-%m-%d" sobre fecha).
         Contar la cantidad de internaciones por día/sector.
      3. $group por sector, calcular $avg del conteo diario.
      4. $project: sector, promedio_diario (redondeado a 2 decimales).

    Llamar a _get_db(). Retornar lista de {sector, promedio_diario}.
    """
    raise NotImplementedError()


def registrar_derivacion(paciente_id: str, medico_origen: str, especialidad_destino: str, motivo: str) -> dict:
    """
    [OP-5] Inserta un documento histórico con el cierre de la derivación.

    Construir documento con:
      - paciente_id, medico_origen, especialidad_destino, motivo
      - fecha: datetime.now(timezone.utc)
      - estado: "cerrada" (indica que la derivación ya se completó)

    Insertar en la colección 'derivaciones' con insert_one.

    (Nota: No confundir con registrar_derivacion_historica, que usa estado "pendiente".
     Esta función registra el cierre exitoso de la derivación.)

    Llamar a _get_db(). Retornar {"mensaje": "...", "paciente_id": paciente_id}.
    """
    raise NotImplementedError()
