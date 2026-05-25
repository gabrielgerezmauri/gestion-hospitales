import json
from datetime import datetime, timezone
from config.database import db_redis


def _get_redis():
    if db_redis is None:
        raise ConnectionError("Redis no está disponible. Verifique que el contenedor esté corriendo.")
    return db_redis


# ──────────────────────────────────────────────
# Gestión de Camas (HASH)
# ──────────────────────────────────────────────

def ingresar_paciente_cama(hospital_id: str, paciente_id: str) -> dict:
    """
    Busca una cama disponible en el hospital y actualiza su estado a 'ocupada'.

    1. Obtener todas las camas del hospital haciendo SCAN 0 MATCH cama:{hospital_id}:*.
    2. Iterar sobre las claves obtenidas, hacer HGETALL c/u y filtrar
       aquellas cuyo campo "estado" sea "disponible".
    3. De la primera cama disponible, hacer HSET para setear:
         - estado -> "ocupada"
         - paciente_id -> paciente_id
         - fecha_ingreso -> datetime.now(timezone.utc).isoformat()
    4. Si no hay camas disponibles, lanzar RuntimeError("No hay camas disponibles").

    Llamar a _get_redis(). Retornar {"cama": numero_cama, "sector": sector}.
    """
    raise NotImplementedError()


def dar_alta_cama(hospital_id: str, numero_cama: str) -> dict:
    """
    Cambia el estado de una cama a 'en_limpieza' tras el alta del paciente.

    1. Construir clave: cama:{hospital_id}:{numero_cama}
    2. Hacer HSET para actualizar:
         - estado -> "en_limpieza"
         - paciente_id -> "" (vacío)
         - fecha_egreso -> datetime.now(timezone.utc).isoformat()

    Llamar a _get_redis(). Retornar {"mensaje": "...", "cama": numero_cama}.
    """
    raise NotImplementedError()


def obtener_ocupacion_tiempo_real(hospital_id: str) -> dict:
    """
    [OP-3] Devuelve métricas en tiempo real de ocupación de camas agrupadas por sector.

    1. SCAN 0 MATCH cama:{hospital_id}:* para obtener todas las camas.
    2. Para cada clave, HGETALL y extraer los campos "sector" y "estado".
    3. Agrupar en memoria por sector:
         - total: cantidad de camas en ese sector
         - ocupadas: camas con estado "ocupada"
         - disponibilidad: total - ocupadas
    4. Calcular también un resumen global:
         - total_camas, total_ocupadas, porcentaje_ocupacion.

    Llamar a _get_redis(). Retornar {sectores: [...], resumen: {...}}.
    """
    raise NotImplementedError()


# ──────────────────────────────────────────────
# Cola de Urgencias (SORTED SET)
# ──────────────────────────────────────────────

def encolar_urgencia(hospital_id: str, paciente_id: str, nivel_urgencia: int, timestamp: float) -> dict:
    """
    [OP-2] Agrega un paciente a la cola de urgencias usando ZADD.

    Clave: urgencias:{hospital_id}
    Score: Se debe calcular como prioridad combinada:
           score = (nivel_urgencia * 1000000) + (timestamp * -1)
           Esto permite que mayor nivel_urgencia tenga mayor score,
           y a igual nivel, el más antiguo (timestamp menor) tenga prioridad.

    Miembro del sorted set: paciente_id (string).
    Usar ZADD con el score calculado.

    Llamar a _get_redis(). Retornar {"mensaje": "...", "paciente_id": paciente_id}.
    """
    raise NotImplementedError()


def obtener_proximo_paciente(hospital_id: str) -> str | None:
    """
    [OP-2] Retorna el paciente con mayor prioridad sin sacarlo de la cola.

    Clave: urgencias:{hospital_id}
    Usar ZREVRANGE con start=0, end=0 para obtener el elemento con mayor score.
    Si la cola está vacía, retornar None.

    Llamar a _get_redis(). Retornar el paciente_id o None.
    """
    raise NotImplementedError()


# ──────────────────────────────────────────────
# Disponibilidad de Médicos (SET)
# ──────────────────────────────────────────────

def obtener_medicos_disponibles(especialidad: str) -> list:
    """
    [OP-2][OP-5] Retorna los médicos disponibles para una especialidad.

    Clave: medicos:{especialidad}
    Usar SMEMBERS para obtener todos los miembros del SET.

    Cada miembro debe ser un JSON string con: {medico_id, nombre, activo}.
    Retornar lista de diccionarios parseados desde JSON.

    Llamar a _get_redis(). Retornar list[{medico_id, nombre, activo}].
    """
    raise NotImplementedError()


# ──────────────────────────────────────────────
# Caché de Historial (STRING con TTL)
# ──────────────────────────────────────────────

def obtener_cache_historial(paciente_id: str) -> dict | None:
    """
    Obtiene el historial del paciente desde la caché Redis.

    Clave: historial:{paciente_id}
    Usar GET para obtener el valor.
    Si existe, parsear el JSON y retornar el dict.
    Si no existe (None), retornar None (cache miss).

    Llamar a _get_redis().
    """
    raise NotImplementedError()


# ──────────────────────────────────────────────
# Eventos Críticos (STREAM)
# ──────────────────────────────────────────────

def publicar_evento(hospital_id: str, tipo_evento: str, datos: dict) -> dict:
    """
    [OP-4][OP-5] Publica una alerta o evento de derivación en el stream de Redis.

    Clave: eventos:{hospital_id}
    Construir el mensaje combinando tipo_evento, datos, y un timestamp actual:
      - tipo: tipo_evento
      - datos: json.dumps(datos)
      - timestamp: datetime.now(timezone.utc).isoformat()

    Usar XADD para agregar la entrada al stream.
    Retornar el ID de la entrada generada por Redis.

    Llamar a _get_redis(). Retornar {"evento_id": entry_id, "mensaje": "..."}.
    """
    raise NotImplementedError()
