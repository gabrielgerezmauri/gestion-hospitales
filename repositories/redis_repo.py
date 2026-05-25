import json
from datetime import datetime, timezone
from config.database import db_redis


def _get_redis():
    if db_redis is None:
        raise ConnectionError("Redis no está disponible. Verifique que el contenedor esté corriendo.")
    return db_redis


def encolar_paciente_derivado(paciente_id, hospital_destino_id, especialidad_destino):
    try:
        r = _get_redis()

        camas_key = f"camas:{hospital_destino_id}:{especialidad_destino}"
        camas_disponibles = r.get(camas_key)
        if camas_disponibles is not None and int(camas_disponibles) <= 0:
            raise RuntimeError(f"No hay camas disponibles en {hospital_destino_id} para {especialidad_destino}")

        cola_key = f"cola_derivaciones:{hospital_destino_id}"
        r.lpush(cola_key, json.dumps({
            "paciente_id": paciente_id,
            "especialidad_destino": especialidad_destino,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }))

        if camas_disponibles is not None:
            r.decr(camas_key)

        return {"mensaje": "Paciente encolado correctamente en Redis"}
    except ConnectionError:
        raise
    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError(f"Error al encolar paciente derivado en Redis: {str(e)}") from e


def quitar_paciente_cola(paciente_id, hospital_destino_id):
    try:
        r = _get_redis()
        cola_key = f"cola_derivaciones:{hospital_destino_id}"
        pacientes = r.lrange(cola_key, 0, -1)
        for p in pacientes:
            data = json.loads(p)
            if data.get("paciente_id") == paciente_id:
                r.lrem(cola_key, 1, p)
                break
        return {"mensaje": "Paciente quitado de la cola en Redis"}
    except ConnectionError:
        raise
    except Exception as e:
        raise RuntimeError(f"Error al quitar paciente de cola en Redis: {str(e)}") from e


def publicar_evento_exitoso(paciente_id, hospital_destino_id, especialidad_destino, medico_derivante_id, motivo):
    try:
        r = _get_redis()
        evento = {
            "tipo": "derivacion_exitosa",
            "paciente_id": paciente_id,
            "hospital_destino_id": hospital_destino_id,
            "especialidad_destino": especialidad_destino,
            "medico_derivante_id": medico_derivante_id,
            "motivo": motivo,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        r.xadd("stream:derivaciones", evento)
        return {"mensaje": "Evento publicado en stream:derivaciones"}
    except ConnectionError:
        raise
    except Exception as e:
        raise RuntimeError(f"Error al publicar evento en Redis Stream: {str(e)}") from e
