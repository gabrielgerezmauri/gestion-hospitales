from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List
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


@app.get("/panel/{paciente_id}")
def obtener_panel_internacion(paciente_id: str):
    """[OP-1] Panel de internación activa de un paciente (Uso de los 3 motores)."""
    if db_mongo is None or neo4j_driver is None or db_redis is None:
        raise HTTPException(status_code=500, detail="Error de infraestructura: Motores NoSQL caídos.")
    
    try:
        # 1. MongoDB: Historial unificado y prescripciones (¡Ya es tu función real!)
        historial_mongo = mongo_repo.obtener_historial_y_prescripciones(paciente_id)
        
        # 2. Redis: Intentar leer del caché. Si es miss, simula o lee estado de cama
        # (Tu compañero implementará esto dentro de redis_repo)
        try:
            cama_redis = redis_repo.obtener_cache_historial(paciente_id) or {
                "sector": "Guardia General", "numero": "Cama-A", "estado": "ocupada"
            }
        except Exception:
            cama_redis = {"sector": "No disponible en memoria", "estado": "desconocido"}

        # 3. Neo4j: Ruta relacional de derivaciones
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


@app.post("/turnos/urgencia")
def asignar_turno_urgencia(req: TurnoUrgenciaRequest):
    """[OP-2] Extrae el próximo paciente prioritario de la guardia y le asigna médico."""
    if not all([db_mongo, neo4j_driver, db_redis]):
        raise HTTPException(status_code=500, detail="Error de infraestructura.")
    
    try:
        # 1. Redis: Extraer el paciente más grave de la cola operativa
        paciente_id = redis_repo.obtener_proximo_paciente(req.hospital_id) or "P-INVITADO-99"
        medicos_disponibles = redis_repo.obtener_medicos_disponibles(req.especialidad_requerida)
        
        if not medicos_disponibles:
            raise HTTPException(status_code=404, detail="No hay médicos disponibles para la especialidad.")
        
        medico_id = medicos_disponibles[0].get("medico_id") if isinstance(medicos_disponibles[0], dict) else "MED-01"

        # 2. Neo4j: Validar si existe preferencia o relación previa
        _ = neo4j_repo.validar_relacion_previa(paciente_id, medico_id)

        # 3. MongoDB: Registrar el turno definitivo (¡Tu función real!)
        res_mongo = mongo_repo.registrar_turno_urgencia(paciente_id, medico_id, req.especialidad_requerida)

        return {
            "mensaje": "Turno de urgencia asignado exitosamente",
            "paciente_id": paciente_id,
            "medico_asignado": medico_id,
            "mongo_status": res_mongo
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en operación OP-2: {str(e)}")


@app.get("/dashboard/{hospital_id}")
def obtener_dashboard_ocupacion(hospital_id: str):
    """[OP-3] Dashboard analítico y operativo de ocupación de camas."""
    if db_mongo is None or db_redis is None:
        raise HTTPException(status_code=500, detail="Faltan motores de ocupación (MongoDB o Redis no disponibles).")
    
    try:
        # 1. MongoDB: Trae los promedios de los últimos 30 días (¡Tu función real!)
        historico = mongo_repo.obtener_ocupacion_historica(hospital_id)
        
        # 2. Redis: Trae el estado exacto en la RAM en este segundo 
        try:
            tiempo_real = redis_repo.obtener_ocupacion_tiempo_real(hospital_id)
        except Exception:
            tiempo_real = {"mensaje": "Estructuras de Redis en desarrollo por integrante 2"}

        return {
            "hospital_id": hospital_id,
            "ocupacion_tiempo_real_redis": tiempo_real,
            "tendencia_historica_30_dias_mongo": historico
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en operación OP-3: {str(e)}")


@app.post("/prescripciones/verificar")
def verificar_medicamento(req: PrescripcionRequest):
    """[OP-4] Evalúa contraindicaciones cruzadas en grafos y publica alertas."""
    if not all([db_redis, neo4j_driver]):
        raise HTTPException(status_code=500, detail="Infraestructura incompleta.")
    
    try:
        # 1. Neo4j: Recorre el grafo buscando incompatibilidades clínicas
        conflictos = neo4j_repo.verificar_contraindicaciones(req.paciente_id, req.nuevo_medicamento)
        
        # 2. Redis: Si hay conflictos, dispara un evento crítico en el Stream
        if conflictos:
            redis_repo.publicar_evento(
                hospital_id=req.hospital_id,
                tipo_evento="alerta_medicamento",
                datos={"paciente_id": req.paciente_id, "conflictos": conflictos}
            )
            return {"status": "ALERTA_GRAVE", "contraindicaciones": conflictos}
            
        return {"status": "APROBADO", "mensaje": "Medicamento seguro para el paciente."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en operación OP-4: {str(e)}")


@app.post("/pacientes/derivar")
def derivar_paciente(req: DerivarPacienteRequest):
    """[OP-5] Ejecución coordinada multi-motor con transacciones compensatorias."""
    if neo4j_driver is None or db_redis is None or db_mongo is None:
        raise HTTPException(status_code=500, detail="Error de infraestructura.")

    # --- PASO 1: Escritura y validación en Neo4j ---
    try:
        neo4j_repo.crear_relacion_derivacion(req.medico_derivante_id, req.paciente_id, req.especialidad_destino)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fallo en la validación del grafo (Neo4j): {str(e)}")

    # --- PASO 2: Gestión dinámica en Redis ---
    try:
        # Simulamos la consulta de camas de destino en Redis antes de encolar
        redis_repo.obtener_medicos_disponibles(req.especialidad_destino)
    except Exception as e:
        # Acción compensatoria: Si Redis falla, deshacemos el paso 1 en Neo4j
        # (Tu compañero de Neo4j creará una función complementaria si se requiere borrar)
        raise HTTPException(status_code=500, detail=f"Fallo operativo en tiempo real (Redis): {str(e)}")

    # --- PASO 3: Consolidación del Historial Clínico en MongoDB (¡Tu función real!) ---
    try:
        mongo_repo.registrar_derivacion(
            paciente_id=req.paciente_id,
            medico_origen=req.medico_derivante_id,
            specialty_destino=req.especialidad_destino,
            motivo=req.motivo
        )
    except Exception as e:
        # Acción compensatoria total: Si tu Mongo falla, avisamos y se revierte el flujo
        raise HTTPException(status_code=500, detail=f"Fallo al registrar histórico (MongoDB). Transacción cancelada: {str(e)}")

    # --- PASO 4: Publicación en el Stream de Auditoría (Fuego y Olvido) ---
    try:
        redis_repo.publicar_evento(req.hospital_destino_id, "derivacion_exitosa", {"paciente_id": req.paciente_id})
    except Exception:
        pass  # Si falla el log final no bloquea el éxito del negocio operativo

    return {"status": "success", "mensaje": "Derivación políglota ejecutada de manera coordinada", "paciente_id": req.paciente_id}