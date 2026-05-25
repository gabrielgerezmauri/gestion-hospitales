from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from config.database import db_mongo, neo4j_driver, db_redis
from repositories import neo4j_repo, redis_repo, mongo_repo

app = FastAPI(title="Capa Persistencia Políglota - Red de Hospitales Públicos")


class DerivarPacienteRequest(BaseModel):
    paciente_id: str
    medico_derivante_id: str
    especialidad_destino: str
    hospital_destino_id: str
    motivo: str

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

# OP-1: Panel de internación activa de un paciente (*) 3 motores
# @app.get("/panel/{paciente_id}")
# def obtener_panel_internacion(paciente_id: str):
#     # Validamos que los motores requeridos estén vivos
#     if not all([db_mongo, neo4j_driver, db_redis]):
#         raise HTTPException(status_code=500, detail="Error de infraestructura: Uno o más motores están caídos.") [cite: 156]
    
#     try:
#         # TODO: Acá va la lógica políglota combinando los 3 repositorios
#         # 1. Buscar historial en Mongo [cite: 117]
#         # 2. Buscar ruta de derivaciones en Neo4j [cite: 118]
#         # 3. Buscar estado de cama en Redis [cite: 119]
#         return {
#             "paciente_id": paciente_id,
#             "mensaje": "Endpoint base listo para la lógica de negocio."
#         }
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Error al procesar la operación: {str(e)}") [cite: 156]
@app.get("/panel/{paciente_id}")
def obtener_panel_internacion(paciente_id: str):
    """OP-1: Panel de internación activa de un paciente (Uso de los 3 motores)."""
    try:
        # Simulamos lo que devolverían tus repositorios por ahora para que no pinche el ASGI
        datos_operativos_redis = {
            "hospital_id": "HOSP-01",
            "sector": "Guardia Adultos",
            "cama_numero": "B-14",
            "estado": "ocupada"
        }
        
        datos_historicos_mongo = {
            "nombre": "Gabriel Gerez",
            "edad": 20,
            "antecedentes": ["Asma crónico"],
            "ultima_consulta": "2026-05-10"
        }
        
        datos_relaciones_neo4j = {
            "medico_cabecera": "Dr. Martínez",
            "derivado_por": "Dr. Gómez",
            "ruta_atencion": ["Guardia", "Traumatología", "Internación"]
        }

        # Armamos la respuesta políglota unificada
        return {
            "paciente_id": paciente_id,
            "estado_actual_tiempo_real_redis": datos_operativos_redis,
            "historial_clinico_mongo": datos_historicos_mongo,
            "red_derivaciones_neo4j": datos_relaciones_neo4j
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al procesar el panel: {str(e)}")

@app.post("/pacientes/derivar", status_code=200)
def derivar_paciente(req: DerivarPacienteRequest):
    if not all([neo4j_driver, db_redis, db_mongo]):
        raise HTTPException(status_code=500, detail="Error de infraestructura: Uno o más motores están caídos.")

    try:
        neo4j_repo.crear_relacion_derivacion(
            req.paciente_id, req.hospital_destino_id,
            req.medico_derivante_id, req.especialidad_destino, req.motivo
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en Neo4j: {str(e)}")

    try:
        redis_repo.encolar_paciente_derivado(
            req.paciente_id, req.hospital_destino_id, req.especialidad_destino
        )
    except Exception as e:
        try:
            neo4j_repo.eliminar_relacion_derivacion(req.paciente_id, req.hospital_destino_id)
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"Error en Redis: {str(e)}")

    try:
        mongo_repo.registrar_derivacion_historica(
            req.paciente_id, req.medico_derivante_id,
            req.especialidad_destino, req.hospital_destino_id, req.motivo
        )
    except Exception as e:
        try:
            redis_repo.quitar_paciente_cola(req.paciente_id, req.hospital_destino_id)
        except Exception:
            pass
        try:
            neo4j_repo.eliminar_relacion_derivacion(req.paciente_id, req.hospital_destino_id)
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"Error en MongoDB: {str(e)}")

    try:
        redis_repo.publicar_evento_exitoso(
            req.paciente_id, req.hospital_destino_id,
            req.especialidad_destino, req.medico_derivante_id, req.motivo
        )
    except Exception:
        pass

    return {"mensaje": "Paciente derivado correctamente", "paciente_id": req.paciente_id}