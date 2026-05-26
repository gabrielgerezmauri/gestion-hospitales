import json
from datetime import datetime, timezone
from config.database import db_redis

def _get_redis():
    if db_redis is None:
        raise ConnectionError(
            "Redis no está disponible. Verifique que el contenedor esté corriendo."
        )
    return db_redis

# ──────────────────────────────────────────────
# 3.1 Gestión de Camas (HASH)
# ──────────────────────────────────────────────

def ingresar_paciente_cama(hospital_id: str, paciente_id: str) -> dict:
    """[3.1.2.a] Registrar ingreso de un paciente a una cama."""
    r = _get_redis()
    patron = f"cama:{hospital_id}:*"

    for key in r.scan_iter(match=patron):
        cama = r.hgetall(key)
        if cama.get("estado") == "disponible":
            numero_cama = cama.get("numero") or key.split(":")[-1]
            sector = cama.get("sector", "Sin sector")

            r.hset(key, mapping={
                "estado": "ocupada",
                "paciente_id": paciente_id,
                "fecha_ingreso": datetime.now(timezone.utc).isoformat()
            })
            return {
                "mensaje": "Paciente internado correctamente.",
                "cama": numero_cama,
                "sector": sector,
                "estado": "ocupada"
            }
    raise RuntimeError("No hay camas disponibles")

def dar_alta_cama(hospital_id: str, numero_cama: str) -> dict:
    """[3.1.2.b] Registrar alta de un paciente (Pasa a en_limpieza)."""
    r = _get_redis()
    key = f"cama:{hospital_id}:{numero_cama}"
    if not r.exists(key):
        raise KeyError(f"No existe la cama {numero_cama}")

    r.hset(key, mapping={
        "estado": "en_limpieza",
        "paciente_id": "",
        "fecha_egreso": datetime.now(timezone.utc).isoformat()
    })
    return {"mensaje": "Alta registrada. Cama en limpieza.", "estado": "en_limpieza"}

def marcar_cama_disponible(hospital_id: str, numero_cama: str) -> dict:
    """[3.1.2.c] Marcar una cama como disponible luego de la limpieza."""
    r = _get_redis()
    key = f"cama:{hospital_id}:{numero_cama}"
    if not r.exists(key):
        raise KeyError(f"No existe la cama {numero_cama}")

    r.hset(key, mapping={
        "estado": "disponible",
        "paciente_id": ""
    })
    # Removemos campos de egreso/ingreso viejos si existen
    r.hdel(key, "fecha_ingreso", "fecha_egreso")
    return {"mensaje": "Cama lista y disponible.", "estado": "disponible"}

def consultar_camas_disponibles_sector(hospital_id: str, sector: str) -> list:
    """[3.1.2.d] Consultar todas las camas disponibles en un sector determinado."""
    r = _get_redis()
    patron = f"cama:{hospital_id}:*"
    disponibles = []

    for key in r.scan_iter(match=patron):
        cama = r.hgetall(key)
        if cama.get("sector") == sector and cama.get("estado") == "disponible":
            cama["numero"] = cama.get("numero") or key.split(":")[-1]
            disponibles.append(cama)
    return disponibles

def obtener_ocupacion_tiempo_real(hospital_id: str) -> dict:
    """[3.1.2.e][OP-3] Porcentaje de ocupación actual por sector y hospital."""
    r = _get_redis()
    patron = f"cama:{hospital_id}:*"
    sectores = {}
    total_camas = 0
    total_ocupadas = 0

    for key in r.scan_iter(match=patron):
        cama = r.hgetall(key)
        sector = cama.get("sector", "Sin sector")
        estado = cama.get("estado", "desconocido")

        if sector not in sectores:
            sectores[sector] = {"sector": sector, "total": 0, "ocupadas": 0, "disponibles": 0}

        sectores[sector]["total"] += 1
        total_camas += 1
        if estado == "ocupada":
            sectores[sector]["ocupadas"] += 1
            total_ocupadas += 1
        elif estado == "disponible":
            sectores[sector]["disponibles"] += 1

    for s in sectores.values():
        s["porcentaje_sector"] = round((s["ocupadas"] / s["total"]) * 100, 2) if s["total"] > 0 else 0

    porcentaje_global = round((total_ocupadas / total_camas) * 100, 2) if total_camas > 0 else 0
    return {
        "hospital_id": hospital_id,
        "sectores": list(sectores.values()),
        "resumen_global": {"total_camas": total_camas, "ocupadas": total_ocupadas, "porcentaje_ocupacion": porcentaje_global}
    }

# ──────────────────────────────────────────────
# 3.2 Cola de Urgencias (SORTED SET)
# ──────────────────────────────────────────────

def encolar_urgencia(hospital_id: str, paciente_id: str, nivel_urgencia: int, timestamp: float) -> dict:
    """[3.2.4.a][OP-2] Agregar un paciente a la cola de urgencias."""
    r = _get_redis()
    key = f"urgencias:{hospital_id}"
    score = (nivel_urgencia * 1_000_000) - timestamp
    r.zadd(key, {paciente_id: score})
    return {"paciente_id": paciente_id, "score": score}

def obtener_proximo_paciente(hospital_id: str) -> str | None:
    """[3.2.4.b][OP-2] Retorna el próximo paciente sin removerlo."""
    r = _get_redis()
    key = f"urgencias:{hospital_id}"
    resultado = r.zrevrange(key, 0, 0)
    return resultado[0] if resultado else None

def confirmar_atencion_paciente(hospital_id: str, paciente_id: str) -> bool:
    """[3.2.4.c] Confirmar la atención de un paciente (Removerlo de la cola)."""
    r = _get_redis()
    key = f"urgencias:{hospital_id}"
    return r.zrem(key, paciente_id) > 0

def listar_pacientes_espera(hospital_id: str) -> list:
    """[3.2.4.d] Listar todos los pacientes en espera ordenados por prioridad."""
    r = _get_redis()
    key = f"urgencias:{hospital_id}"
    # Devolvemos los miembros con sus scores ordenados de mayor a menor prioridad
    resultado = r.zrevrange(key, 0, -1, withscores=True)
    return [{"paciente_id": x[0], "prioridad_score": x[1]} for x in resultado]

def consultar_posicion_cola(hospital_id: str, paciente_id: str) -> int | None:
    """[3.2.4.e] Consultar la posición en la cola de un paciente (0 = el próximo a ser atendido)."""
    r = _get_redis()
    key = f"urgencias:{hospital_id}"
    pos = r.zrevrank(key, paciente_id)
    return pos if pos is not None else None

# ──────────────────────────────────────────────
# 3.3 Disponibilidad de Médicos (SET)
# ──────────────────────────────────────────────

def set_disponibilidad_medico(especialidad: str, matricula: str, disponible: bool):
    """[3.3.6.a] Marcar un médico como disponible o no disponible."""
    r = _get_redis()
    key = f"medicos:{especialidad}"
    if disponible:
        r.sadd(key, matricula)
    else:
        r.srem(key, matricula)

def obtener_medicos_disponibles(especialidad: str) -> list:
    """[3.3.6.b] Obtener todos los médicos disponibles para una especialidad."""
    r = _get_redis()
    key = f"medicos:{especialidad}"
    return list(r.smembers(key))

def obtener_medicos_interseccion(especialidades: list) -> list:
    """[3.3.6.c] Obtener médicos disponibles para múltiples especialidades simultáneamente."""
    r = _get_redis()
    claves = [f"medicos:{esp}" for esp in especialidades]
    if not claves:
        return []
    return list(r.sinter(claves))

def consultar_cantidad_especialidades_medico(matricula: str) -> int:
    """[3.3.6.d] Consultar en cuántas especialidades está disponible un médico."""
    r = _get_redis()
    conteo = 0
    for key in r.scan_iter(match="medicos:*"):
        if r.sismember(key, matricula):
            conteo += 1
    return conteo

# ──────────────────────────────────────────────
# 3.4 Caché de Historial Clínico (STRING con TTL)
# ──────────────────────────────────────────────

def guardar_cache_historial(paciente_id: str, historial_dict: dict):
    """[3.4.8.a] Guardar historial serializado en Redis con TTL de 24 horas (86400 segundos)."""
    r = _get_redis()
    key = f"historial:{paciente_id}"
    r.setex(key, 86400, json.dumps(historial_dict, ensure_ascii=False))

def obtener_cache_historial(paciente_id: str) -> dict | None:
    """[3.4.8.b] Leer historial de la caché."""
    r = _get_redis()
    key = f"historial:{paciente_id}"
    valor = r.get(key)
    return json.loads(valor) if valor else None

def invalidar_cache_historial(paciente_id: str):
    """[3.4.8.c] Al dar de alta: invalidar explícitamente su entrada en el caché."""
    r = _get_redis()
    key = f"historial:{paciente_id}"
    r.delete(key)

# ──────────────────────────────────────────────
# 3.5 Stream de Eventos Críticos (STREAM)
# ──────────────────────────────────────────────

def publicar_evento(hospital_id: str, tipo_evento: str, paciente_id: str, medico_id: str, detalle: str) -> str:
    """[3.5.10.a] Publicar un evento estructurado en el stream."""
    r = _get_redis()
    key = "eventos:sistema:stream"  # Unificamos clave para poder auditar globalmente
    mensaje = {
        "tipo": tipo_evento,
        "hospital_id": hospital_id,
        "paciente_id": paciente_id,
        "medico_id": medico_id or "N/A",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "detalle": detalle
    }
    return r.xadd(key, mensaje)

def consumir_ultimos_eventos(n: int) -> list:
    """[3.5.10.b] Consumir los últimos N eventos del stream para auditoría."""
    r = _get_redis()
    key = "eventos:sistema:stream"
    # xrevrange con count=N nos da los últimos N de forma directa
    return r.xrevrange(key, max="+", min="-", count=n)

def consumir_eventos_por_tipo_y_rango(tipo_evento: str, timestamp_inicio: str, timestamp_fin: str) -> list:
    """[3.5.10.c] Consumir eventos de un tipo específico en un rango de tiempo."""
    r = _get_redis()
    key = "eventos:sistema:stream"
    
    # Redis usa IDs basados en milisegundos para rangos (ej: 1716663600000)
    eventos_rango = r.xrange(key, start=timestamp_inicio, end=timestamp_fin)
    
    # Filtramos por el tipo de evento pedido
    filtrados = []
    for entry_id, campo in eventos_rango:
        if campo.get("tipo") == tipo_evento:
            filtrados.append({"id": entry_id, "datos": campo})
    return filtrados