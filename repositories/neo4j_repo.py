from config.database import neo4j_driver


def _get_driver():
    if neo4j_driver is None:
        raise ConnectionError("Neo4j no está disponible. Verifique que el contenedor esté corriendo.")
    return neo4j_driver


def obtener_red_paciente(paciente_id: str) -> dict:
    """
    [OP-1] Retorna la red de atención del paciente: médicos previos y ruta de derivaciones.

    Ejecutar una consulta Cypher que:
      1. MATCH (p:Paciente {id: $paciente_id})
      2. OPTIONAL MATCH (p)-[:ATENDIDO_POR]->(m:Medico)
         RETURN m.id, m.nombre, m.especialidad
      3. OPTIONAL MATCH path = (p)-[:DERIVADO_A*1..3]->(h:Hospital)
         RETURN nodes(path) AS ruta_derivaciones

    Agrupar resultados:
      - medicos_previos: lista de {id, nombre, especialidad}
      - ruta_derivaciones: lista de hospitales en la cadena de derivación

    Usar driver.session() como contexto manager.
    Llamar a _get_driver(). Retornar dict con ambas claves.
    """
    raise NotImplementedError()


def validar_relacion_previa(paciente_id: str, medico_id: str) -> bool:
    """
    [OP-2] Verifica si el médico ya atendió al paciente anteriormente.

    Consulta Cypher:
      MATCH (p:Paciente {id: $paciente_id})-[:ATENDIDO_POR]->(m:Medico {id: $medico_id})
      RETURN count(m) > 0 AS existe_relacion

    Usar session.run() y obtener el escalar booleano del único registro.
    Llamar a _get_driver(). Retornar True/False.
    """
    raise NotImplementedError()


def verificar_contraindicaciones(paciente_id: str, nuevo_medicamento: str) -> list:
    """
    [OP-4] Cruza las prescripciones activas del paciente con el grafo de
    incompatibilidades médicas y devuelve los pares graves encontrados.

    Pasos:
      1. Obtener las prescripciones activas del paciente desde MongoDB
         (reutilizando obtener_prescripciones_activas de mongo_repo).
      2. Extraer la lista de medicamentos activos.
      3. Para cada medicamento activo, ejecutar Cypher:
           MATCH (m1:Medicamento {nombre: $activo})-[r:INCOMPATIBLE_CON]->(m2:Medicamento {nombre: $nuevo})
           RETURN m1.nombre AS medicamento_activo, m2.nombre AS medicamento_nuevo,
                  r.gravedad AS gravedad, r.efecto AS efecto
         (La relación INCOMPATIBLE_CON tiene propiedades: gravedad, efecto)
      4. Filtrar solo aquellos donde gravedad sea "grave" o "moderada".
      5. Retornar lista de dicts: {medicamento_activo, medicamento_nuevo, gravedad, efecto}.

    Llamar a _get_driver(). Si no hay prescripciones activas, retornar [].
    """
    raise NotImplementedError()


def crear_relacion_derivacion(medico_origen: str, paciente_id: str, especialidad_destino: str) -> dict:
    """
    [OP-5] Crea una relación DERIVA_A entre un médico y un paciente hacia
    una especialidad destino, validando que no exista una activa al mismo destino.

    Consulta Cypher:
      1. MATCH (m:Medico {id: $medico_origen})
         MATCH (p:Paciente {id: $paciente_id})
      2. Verificar que NO exista:
           (p)-[:DERIVA_A {especialidad_destino: $especialidad_destino, activa: true}]->()
         Si existe, lanzar RuntimeError con mensaje de derivación activa.
      3. MERGE (m)-[r:DERIVA_A]->(p)
         SET r.especialidad_destino = $especialidad_destino,
             r.fecha = datetime(),
             r.activa = true
         RETURN r

    (Nota: Esta función usa el médico como nodo origen, a diferencia de la
     función crear_relacion_derivacion existente que usa paciente->hospital.)

    Llamar a _get_driver(). Retornar {"mensaje": "...", "relacion": "DERIVA_A"}.
    """
    raise NotImplementedError()
