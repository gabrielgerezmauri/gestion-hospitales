from datetime import datetime, timezone, timedelta
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

"""
El poder de $facet: En una base de datos tradicional, para armar esta pantalla tendrías que haber hecho dos consultas separadas a la base de datos (una query para el historial y otra para los remedios). $facet procesa la misma colección de consultas en paralelo dentro de la memoria del servidor de MongoDB y te trae todo resuelto en un solo viaje de red.

Lógica temporal con $dateAdd: Como tus JSON semilla tienen fechas de inicio y duraciones en días (por ejemplo: duracion_dias: 7), calculamos dinámicamente la fecha_fin sumándole esos días a la fecha de la consulta. Si esa fecha calculada es mayor o igual a ahora, el medicamento se considera activo.
"""
def obtener_historial_y_prescripciones(paciente_id: str) -> dict:
    """
    [OP-1] Obtiene el historial clínico resumido y las prescripciones activas
    del paciente en un único viaje a la base de datos usando $facet.
    """
    try:
        db = _get_db()
        ahora = datetime.now(timezone.utc)

        pipeline = [
            # 1. Filtramos las consultas que correspondan al paciente solicitado
            {"$match": {"paciente_id": paciente_id}},
            
            # 2. Dividimos el flujo en dos ramas paralelas independientes
            {
                "$facet": {
                    # Rama A: Trae las últimas 5 consultas ordenadas por fecha descendente
                    "ultimas_consultas": [
                        {"$sort": {"fecha": -1}},
                        {"$limit": 5},
                        {
                            "$project": {
                                "_id": 0,
                                "consulta_id": {"$toString": "$_id"},
                                "fecha": 1,
                                "medico_id": 1,
                                "diagnostico": 1,
                                "tratamiento": 1
                            }
                        }
                    ],
                    # Rama B: Descompone las prescripciones y filtra solo las vigentes
                    "prescripciones_activas": [
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
                                "fecha_fin": {"$gte": ahora}
                            }
                        },
                        {
                            "$project": {
                                "_id": 0,
                                "medicamento": "$prescripciones.medicamento",
                                "dosis": "$prescripciones.dosis",
                                "frecuencia": "$prescripciones.frecuencia",
                                "fecha_inicio": "$prescripciones.fecha",
                                "fecha_fin": 1
                            }
                        }
                    ]
                }
            }
        ]

        # Como aggregate devuelve un cursor, lo pasamos a lista.
        # $facet siempre devuelve un único documento con los arrays de cada rama adentro.
        resultado = list(db.consultas.aggregate(pipeline))
        
        if resultado and len(resultado) > 0:
            return resultado[0]
            
        return {"ultimas_consultas": [], "prescripciones_activas": []}

    except ConnectionError:
        raise
    except Exception as e:
        raise RuntimeError(f"Error en agregación políglota OP-1 de MongoDB: {str(e)}") from e

"""
Uso de $push: En el modelo documental, el historial de un paciente es dinámico y crece de forma vertical. El operador $push te permite añadir elementos al final de un array interno 
de forma atómica y ultra eficiente, sin necesidad de leer el documento entero a Python, modificarlo en memoria y volverlo a guardar de forma pesada.  La magia del upsert=True: 
Esta propiedad de MongoDB actúa como un salvavidas operativo. Si es la primera vez que el paciente pisa la red de hospitales, el criterio de búsqueda {"paciente_id": paciente_id} 
no va a encontrar nada. Al estar el upsert activo, MongoDB crea automáticamente el documento base e inyecta el array historial con el turno inicial en una sola instrucción.
"""

def registrar_turno_urgencia(paciente_id: str, medico_id: str, especialidad: str) -> dict:
    """
    [OP-2] Inserta un nuevo turno de urgencia asignado en el historial del paciente
    dentro de la colección 'consultas'.
    """
    try:
        db = _get_db()

        # 1. Definimos el subdocumento con los datos del turno de urgencia
        nuevo_turno = {
            "tipo": "urgencia",
            "medico_id": medico_id,
            "especialidad": especialidad,
            "fecha": datetime.now(timezone.utc),
            "diagnostico": "Pendiente de evaluación en guardia",
            "tratamiento": "En espera"
        }

        # 2. Impactamos en MongoDB usando update_one con $push.
        # Si el documento del paciente no existe, 'upsert=True' lo crea de cero.
        db.consultas.update_one(
            {"paciente_id": paciente_id},
            {
                "$push": {
                    "historial": nuevo_turno
                }
            },
            upsert=True
        )

        return {
            "status": "success",
            "mensaje": "Turno de urgencia registrado en el historial histórico de MongoDB",
            "paciente_id": paciente_id
        }

    except ConnectionError:
        raise
    except Exception as e:
        raise RuntimeError(f"Error al registrar turno de urgencia en MongoDB: {str(e)}") from e

"""
¿Por qué una doble agrupación ($group)? 
Pensalo así: si agrupas directamente por sector en los 30 días, te daría el total acumulado de 
derivaciones de todo el mes, no el promedio por día.

Al agrupar primero por {"sector", "dia"} (usando especialidad_destino y fecha_derivacion), 
hacés que MongoDB consolide fotos diarias (ej: "El 24 de mayo en Cardiología se recibieron 12 derivaciones"). 
En la segunda agrupación, colapsás los días y promediás esos números de forma analítica.

Complejidad en SQL vs. NoSQL: 
Si tuvieras que hacer esto en SQL puro, requerirías hacer uso de subconsultas anidadas o 
subtablas temporales (WITH sector_diario AS (...) SELECT sector, AVG(...)). 
En MongoDB, el framework de agregaciones te permite estructurarlo como una tubería lineal de 
datos (pipeline), haciendo que el código sea mucho más fácil de optimizar y mantener a largo plazo.
"""
def obtener_ocupacion_historica(hospital_id: str) -> list:
    """
    [OP-3] Calcula el promedio diario de ocupación (derivaciones recibidas) 
    por especialidad en los últimos 30 días procesando la colección 'derivaciones'.
    """
    try:
        db = _get_db()
        
        # 1. Calculamos la fecha de corte (30 días atrás a partir de hoy)
        fecha_limite = datetime.now(timezone.utc) - timedelta(days=30)

        pipeline = [
            # Paso 1: Filtramos las derivaciones destinadas a este hospital en los últimos 30 días
            {
                "$match": {
                    "hospital_destino_id": hospital_id,
                    "fecha_derivacion": {"$gte": fecha_limite}
                }
            },
            
            # Paso 2: Agrupamos por la especialidad de destino y por el día exacto (AAAA-MM-DD)
            {
                "$group": {
                    "_id": {
                        "sector": "$especialidad_destino",
                        "dia": { "$dateToString": { "format": "%Y-%m-%d", "date": "$fecha_derivacion" } }
                    },
                    "conteo_diario": { "$sum": 1 }
                }
            },
            
            # Paso 3: Agrupamos por sector para promediar los conteos diarios
            {
                "$group": {
                    "_id": "$_id.sector",
                    "promedio_diario": { "$avg": "$conteo_diario" }
                }
            },
            
            # Paso 4: Proyectamos la salida prolija redondeando a 2 decimales
            {
                "$project": {
                    "_id": 0,
                    "sector": "$_id",
                    "promedio_diario": { "$round": ["$promedio_diario", 2] }
                }
            },
            
            # Paso 5: Ordenamos alfabéticamente
            {
                "$sort": { "sector": 1 }
            }
        ]

        resultado = list(db.derivaciones.aggregate(pipeline))
        return resultado

    except ConnectionError:
        raise
    except Exception as e:
        raise RuntimeError(f"Error al calcular la ocupación histórica en MongoDB: {str(e)}") from e

"""
El rol de Mongo en la consistencia eventual: Cuando se ejecuta la OP-5, intervienen los tres motores en cadena: Neo4j crea la relación, Redis valida las camas/médicos y vos guardás el histórico.
¿Qué pasa si tu query falla? Si los otros dos motores guardaron los datos pero tu insert_one pincha (por ejemplo, porque se cayó el contenedor de Mongo), el orquestador (main.py) va a capturar este RuntimeError.
Inmediatamente va a ejecutar las acciones compensatorias: llamará a Neo4j para borrar la relación que se acababa de crear y a Redis para sacar al paciente de la fila operativa. Así se garantiza que no haya "datos fantasma" en el sistema.  
"""
def registrar_derivacion(paciente_id: str, medico_origen: str, specialty_destino: str, motivo: str) -> dict:
    """
    [OP-5] Inserta un documento histórico en la colección 'derivaciones' que certifica
    el cierre y ejecución exitosa de una derivación médica.
    """
    try:
        db = _get_db()

        # 1. Construimos el documento con los requisitos exactos de la consigna
        nueva_derivacion = {
            "paciente_id": paciente_id,
            "medico_derivante_id": medico_origen,
            "especialidad_destino": specialty_destino,
            "motivo": motivo,
            "fecha": datetime.now(timezone.utc),
            "estado": "cerrada"  # Indica que el circuito políglota se completó con éxito
        }

        # 2. Insertamos el registro histórico en la colección correspondiente
        db.derivaciones.insert_one(nueva_derivacion)

        return {
            "status": "success",
            "mensaje": "Derivación histórica registrada con éxito en MongoDB",
            "paciente_id": paciente_id
        }

    except ConnectionError:
        raise
    except Exception as e:
        raise RuntimeError(f"Error al registrar la derivación en MongoDB: {str(e)}") from e
