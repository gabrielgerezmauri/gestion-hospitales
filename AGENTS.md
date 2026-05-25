# AGENTS.md — Gestión Hospitales (Políglota)

## Stack

- **FastAPI** (Python 3.10+) — REST entrypoint: `main.py:app`
- **MongoDB** (`sistema_hospitalario`) — historial clínico y turnos
- **Neo4j** (neo4j/password123) — red de derivaciones y contraindicaciones
- **Redis** — estado operativo en tiempo real

## Developer commands (order matters)

```bash
docker-compose up -d            # 1. Start MongoDB, Neo4j, Redis containers
pip install -r requirements.txt # 2. Install deps (fastapi, uvicorn, pymongo, neo4j, redis, python-dotenv)
uvicorn main:app --reload       # 3. Dev server at http://localhost:8000
```

## Architecture notes

- DB connections are **module-level** in `config/database.py` — imported at FastAPI startup time
- Connection failures log errors and set driver vars to `None`; they do **not** crash the server
- Health check: `GET /` returns `{status, engines: {mongodb, neo4j, redis}}`
- `repositories/mongo_repo.py`, `repositories/neo4j_repo.py`, `repositories/redis_repo.py` are **empty stubs** — business logic to be implemented
- `.env` in repo root holds all connection strings; `python-dotenv` loads it automatically

## What's NOT configured

No tests, linting, typechecking, CI, or formatter. Do not look for them.
