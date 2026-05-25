from config.database import neo4j_driver


def _get_driver():
    if neo4j_driver is None:
        raise ConnectionError("Neo4j no está disponible. Verifique que el contenedor esté corriendo.")
    return neo4j_driver


def crear_relacion_derivacion(paciente_id, hospital_destino_id, medico_derivante_id, especialidad_destino, motivo):
    try:
        driver = _get_driver()
        with driver.session() as session:
            session.run(
                """
                MATCH (p:Paciente {id: $paciente_id})
                MATCH (h:Hospital {id: $hospital_destino_id})
                MERGE (p)-[r:DERIVADO_A]->(h)
                SET r.medico_derivante_id = $medico_derivante_id,
                    r.especialidad_destino = $especialidad_destino,
                    r.motivo = $motivo,
                    r.fecha = datetime()
                RETURN r
                """,
                paciente_id=paciente_id,
                hospital_destino_id=hospital_destino_id,
                medico_derivante_id=medico_derivante_id,
                especialidad_destino=especialidad_destino,
                motivo=motivo
            )
        return {"mensaje": "Relación de derivación creada en Neo4j"}
    except ConnectionError:
        raise
    except Exception as e:
        raise RuntimeError(f"Error al crear relación de derivación en Neo4j: {str(e)}") from e


def eliminar_relacion_derivacion(paciente_id, hospital_destino_id):
    try:
        driver = _get_driver()
        with driver.session() as session:
            session.run(
                """
                MATCH (p:Paciente {id: $paciente_id})-[r:DERIVADO_A]->(h:Hospital {id: $hospital_destino_id})
                DELETE r
                """,
                paciente_id=paciente_id,
                hospital_destino_id=hospital_destino_id
            )
        return {"mensaje": "Relación de derivación eliminada de Neo4j"}
    except ConnectionError:
        raise
    except Exception as e:
        raise RuntimeError(f"Error al eliminar relación de derivación en Neo4j: {str(e)}") from e
