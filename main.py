import time
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional
from config.database import db_mongo, neo4j_driver, db_redis
from repositories import mongo_repo, redis_repo, neo4j_repo

app = FastAPI(title="Capa Persistencia Políglota - Red de Hospitales Públicos")

# ──────────────────────────────────────────────
# Modelos de Datos (Pydantic Validation)
# ──────────────────────────────────────────────
class TurnoUrgenciaRequest(BaseModel):
    hospital_id: str
    especialidad_requerida: str

class PrescripcionRequest(BaseModel):
    paciente_id: str
    hospital_id: str
    medico_tratante_id: str
    nuevo_medicamento: str

class DerivarPacienteRequest(BaseModel):
    paciente_id: str
    medico_derivante_id: str
    especialidad_destino: str
    hospital_destino_id: str
    motivo: str

# ──────────────────────────────────────────────
# Endpoints de la Aplicación
# ──────────────────────────────────────────────

@app.get("/")
def health_check():
    """Verifica el estado de los motores NoSQL conectados."""
    return {
        "status": "online",
        "engines": {
            "mongodb": "OK" if db_mongo is not None else "DOWN",
            "neo4j": "OK" if neo4j_driver is not None else "DOWN",
            "redis": "OK" if db_redis is not None else "DOWN"
        }
    }


@app.get("/panel/{paciente_id}", tags=["Operaciones Políglotas (Negocio)"])
def obtener_panel_internacion(paciente_id: str):
    """[OP-1] Panel de internación activa de un paciente (Uso de los 3 motores)."""
    if db_mongo is None or neo4j_driver is None or db_redis is None:
        raise HTTPException(status_code=500, detail="Error de infraestructura: Motores NoSQL caídos.")
    
    try:
        # 1. MongoDB: Historial unificado y prescripciones analíticas temporales
        historial_mongo = mongo_repo.obtener_historial_y_prescripciones(paciente_id)
        
        # 2. Redis: Intentar leer del caché real de historial clínico activo
        try:
            cama_redis = redis_repo.obtener_cache_historial(paciente_id)
            if not cama_redis:
                # Si es un cache miss, se asume un estado operativo base de control
                cama_redis = {"sector": "Guardia General", "estado": "internado_sin_cache"}
        except Exception:
            cama_redis = {"sector": "No disponible en memoria (Redis DOWN)", "estado": "desconocido"}

        # 3. Neo4j: Ruta relacional de derivaciones del grafo
        try:
            red_neo4j = neo4j_repo.obtener_red_paciente(paciente_id)
        except Exception:
            red_neo4j = {"medicos_previos": [], "ruta_derivaciones": []}

        return {
            "paciente_id": paciente_id,
            "resumen_clinico": historial_mongo,
            "estado_cama_tiempo_real": cama_redis,
            "red_atencion_grafo": red_neo4j
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en operación OP-1: {str(e)}")


@app.post("/turnos/urgencia", tags=["Operaciones Políglotas (Negocio)"])
def asignar_turno_urgencia(req: TurnoUrgenciaRequest):
    """[OP-2] Extrae el próximo paciente prioritario de la guardia y le asigna médico."""
    if db_mongo is None or neo4j_driver is None or db_redis is None:
        raise HTTPException(status_code=500, detail="Error de infraestructura (Motores NoSQL caídos).")
    
    try:
        # 1. Redis: Extraer el paciente más grave de la cola operativa real (ZSET)
        paciente_id = redis_repo.obtener_proximo_paciente(req.hospital_id)
        if not paciente_id:
            raise HTTPException(status_code=404, detail="No hay pacientes en la cola de urgencias para este hospital.")
            
        medicos_disponibles = redis_repo.obtener_medicos_disponibles(req.especialidad_requerida)
        if not medicos_disponibles:
            raise HTTPException(status_code=404, detail="No hay médicos disponibles en Redis para la especialidad requerida.")
        
        # Como smembers devuelve una lista de strings (matrículas), tomamos el primero directamente
        medico_id = medicos_disponibles[0] if isinstance(medicos_disponibles[0], str) else medicos_disponibles[0].get("medico_id", "MED-01")

        # 2. Neo4j: Validar si existe preferencia o relación previa
        try:
            _ = neo4j_repo.validar_relacion_previa(paciente_id, medico_id)
        except Exception:
            pass # Si la validación relacional falla, se prosigue por protocolo de urgencia absoluta

        # 3. MongoDB: Registrar el turno definitivo en el historial clínico documental
        res_mongo = mongo_repo.registrar_turno_urgencia(paciente_id, medico_id, req.especialidad_requerida)
        
        # 4. Redis: Confirmar la atención removiendo al paciente de la fila operativa (ZREM)
        redis_repo.confirmar_atencion_paciente(req.hospital_id, paciente_id)

        return {
            "mensaje": "Turno de urgencia asignado exitosamente y paciente removido de la cola.",
            "paciente_id": paciente_id,
            "medico_asignado": medico_id,
            "mongo_status": res_mongo
        }
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en operación OP-2: {str(e)}")


@app.get("/dashboard/{hospital_id}", tags=["Operaciones Políglotas (Negocio)"])
def obtener_dashboard_ocupacion(hospital_id: str):
    """[OP-3] Dashboard analítico y operativo de ocupación de camas."""
    if db_mongo is None or db_redis is None:
        raise HTTPException(status_code=500, detail="Faltan motores de ocupación (MongoDB o Redis no disponibles).")
    
    try:
        # 1. MongoDB: Trae los promedios analíticos de los últimos 30 días
        historico = mongo_repo.obtener_ocupacion_historica(hospital_id)
        
        # 2. Redis: Trae el estado exacto real de la RAM de los HASHes de camas
        try:
            tiempo_real = redis_repo.obtener_ocupacion_tiempo_real(hospital_id)
        except Exception as e:
            tiempo_real = {"mensaje": f"Error al recuperar datos en tiempo real de Redis: {str(e)}"}

        return {
            "hospital_id": hospital_id,
            "ocupacion_tiempo_real_redis": tiempo_real,
            "tendencia_historica_30_dias_mongo": historico
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en operación OP-3: {str(e)}")


@app.post("/prescripciones/verificar", tags=["Operaciones Políglotas (Negocio)"])
def verificar_medicamento(req: PrescripcionRequest):
    """[OP-4] Evalúa contraindicaciones cruzadas en grafos y publica alertas en Streams."""
    if db_redis is None or neo4j_driver is None:
        raise HTTPException(status_code=500, detail="Infraestructura incompleta (Redis o Neo4j caídos).")
    
    try:
        # 1. Neo4j: Recorre el grafo buscando incompatibilidades clínicas
        conflictos = neo4j_repo.verificar_contraindicaciones(req.paciente_id, req.nuevo_medicamento)
        
        # 2. Redis: Si hay conflictos, dispara un evento crítico adaptado a la firma del repo expandido (STREAM)
        if conflictos:
            redis_repo.publicar_evento(
                hospital_id=req.hospital_id,
                tipo_evento="alerta_medicamento",
                paciente_id=req.paciente_id,
                medico_id=req.medico_tratante_id,
                detalle=f"Conflicto grave detectado para el fármaco: {req.nuevo_medicamento}. Incompatibilidades: {str(conflictos)}"
            )
            return {"status": "ALERTA_GRAVE", "contraindicaciones": conflictos}
            
        return {"status": "APROBADO", "mensaje": "Medicamento seguro para el paciente."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en operación OP-4: {str(e)}")


@app.post("/pacientes/derivar", tags=["Operaciones Políglotas (Negocio)"])
def derivar_paciente(req: DerivarPacienteRequest):
    """[OP-5] Ejecución coordinada multi-motor con transacciones compensatorias."""
    if neo4j_driver is None or db_redis is None or db_mongo is None:
        raise HTTPException(status_code=500, detail="Error de infraestructura (Motores NoSQL no disponibles).")

    # --- PASO 1: Escritura y validación en Neo4j ---
    try:
        neo4j_repo.crear_relacion_derivacion(req.medico_derivante_id, req.paciente_id, req.especialidad_destino)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fallo en la validación del grafo (Neo4j): {str(e)}")

    # --- PASO 2: Gestión dinámica y reserva en Redis ---
    try:
        # Encolamos al paciente en la cola de prioridad de urgencia del hospital destino (ZSET)
        # Usamos time.time() para el timestamp float que pide la fórmula del score
        redis_repo.encolar_urgencia(
            hospital_id=req.hospital_destino_id,
            paciente_id=req.paciente_id,
            nivel_urgencia=3, # Prioridad media base para pacientes derivados por defecto
            timestamp=time.time()
        )
    except Exception as e:
        # Acción compensatoria: Si Redis falla, deshacemos el paso 1 eliminando la relación en el grafo de Neo4j
        try:
            neo4j_repo.eliminar_relacion_derivacion(req.medico_derivante_id, req.paciente_id)
        except Exception:
            pass # Evitamos enmascarar el error operativo original
        raise HTTPException(status_code=500, detail=f"Fallo operativo en tiempo real (Redis). Flujo revertido: {str(e)}")

    # --- PASO 3: Consolidación del Historial Clínico en MongoDB ---
    try:
        mongo_repo.registrar_derivacion(
            paciente_id=req.paciente_id,
            medico_origen=req.medico_derivante_id,
            specialty_destino=req.especialidad_destino,
            motivo=req.motivo
        )
    except Exception as e:
        # Acción compensatoria total: Si tu Mongo falla, removemos de Redis y de Neo4j para mantener consistencia eventual
        try:
            redis_repo.confirmar_atencion_paciente(req.hospital_destino_id, req.paciente_id) # ZREM
            neo4j_repo.eliminar_relacion_derivacion(req.medico_derivante_id, req.paciente_id)
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"Fallo al registrar histórico (MongoDB). Transacción políglota cancelada y revertida: {str(e)}")

    # --- PASO 4: Publicación en el Stream unificado de Auditoría (Fuego y Olvido) ---
    try:
        redis_repo.publicar_evento(
            hospital_id=req.hospital_destino_id,
            tipo_evento="derivacion_exitosa",
            paciente_id=req.paciente_id,
            medico_id=req.medico_derivante_id,
            detalle=f"Derivación exitosa hacia la especialidad: {req.especialidad_destino}. Motivo: {req.motivo}"
        )
    except Exception:
        pass  # Si falla el log final no bloquea el éxito del negocio operativo principal

    return {"status": "success", "mensaje": "Derivación políglota ejecutada de manera coordinada", "paciente_id": req.paciente_id}


# ──────────────────────────────────────────────
# Endpoints de Control Administrativo (Redis)
# ──────────────────────────────────────────────

@app.post("/admin/camas/disponible", tags=["Administración en Tiempo Real (Redis)"])
def admin_marcar_cama_disponible(hospital_id: str, numero_cama: str):
    """[3.1.2.c] Libera una cama pasándola a disponible post-limpieza."""
    try:
        return redis_repo.marcar_cama_disponible(hospital_id, numero_cama)
    except KeyError as ke:
        raise HTTPException(status_code=404, detail=str(ke))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/admin/camas/buscar-sector", tags=["Administración en Tiempo Real (Redis)"])
def admin_buscar_camas_sector(hospital_id: str, sector: str):
    """[3.1.2.d] Lista todas las camas disponibles en un sector específico."""
    try:
        return redis_repo.consultar_camas_disponibles_sector(hospital_id, sector)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/admin/urgencias/lista", tags=["Administración en Tiempo Real (Redis)"])
def admin_listar_cola_urgencias(hospital_id: str):
    """[3.2.4.d] Muestra el estado actual de la cola de espera por prioridad (ZSET)."""
    try:
        return redis_repo.listar_pacientes_espera(hospital_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/admin/urgencias/posicion", tags=["Administración en Tiempo Real (Redis)"])
def admin_consultar_puesto_cola(hospital_id: str, paciente_id: str):
    """[3.2.4.e] Devuelve el puesto de un paciente (0 significa que es el próximo)."""
    try:
        posicion = redis_repo.consultar_posicion_cola(hospital_id, paciente_id)
        if posicion is None:
            raise HTTPException(status_code=404, detail="El paciente no está en la cola de urgencias.")
        return {"paciente_id": paciente_id, "posicion_en_cola": posicion}
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/admin/medicos/disponibilidad", tags=["Administración en Tiempo Real (Redis)"])
def admin_set_disponibilidad_medico(especialidad: str, matricula: str, disponible: bool):
    """[3.3.6.a] Agrega o remueve la matrícula de un médico en el SET de disponibilidad."""
    try:
        redis_repo.set_disponibilidad_medico(especialidad, matricula, disponible)
        estado = "disponible" if disponible else "no disponible"
        return {"mensaje": f"Médico {matricula} marcado como {estado} para {especialidad}."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/admin/medicos/interseccion", tags=["Administración en Tiempo Real (Redis)"])
def admin_medicos_multi_especialidad(especialidades: List[str] = Query(...)):
    """[3.3.6.c] Cruza múltiples SETs para ver qué médicos cubren todas las especialidades solicitadas (SINTER)."""
    try:
        return redis_repo.obtener_medicos_interseccion(especialidades)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/admin/stream/ultimos", tags=["Administración en Tiempo Real (Redis)"])
def admin_ver_ultimos_eventos(cantidad: int = 10):
    """[3.5.10.b] Trae los últimos N eventos globales del Stream de auditoría del sistema."""
    try:
        eventos = redis_repo.consumir_ultimos_eventos(cantidad)
        # Formateamos la salida para que en el Swagger se lea el diccionario limpio
        return [{"id": x[0], "datos": x[1]} for x in eventos]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))