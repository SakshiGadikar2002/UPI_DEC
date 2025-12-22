# Backend Overview

## Main Files
- `main.py`: FastAPI app entry point, API routing, websocket, and job scheduling.
- `database.py`: PostgreSQL connection, pool management, schema bootstrap, helpers.
- `requirements.txt`: Python dependencies for backend (FastAPI, asyncpg, pandas, etc).

## Key Modules
- `connectors/`: REST and WebSocket connectors for data ingestion.
- `etl/`: Extractor, Transformer, Loader, and JobManager for ETL pipeline.
- `job_scheduler/`: Schedules recurring jobs, alert checks, and email notifications.
- `models/`: Pydantic models for alerts, connectors, websocket data.
- `services/`: Alert manager, notification service, crypto alert engine, etc.
- `routes/`: API endpoints for alerts and system features.

## How to Run
```bash
cd backend
python -m venv .venv
. .venv/Scripts/activate  # Windows PowerShell: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## Environment Variables
```
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=etl_tool
```

## Features
- REST & WebSocket connectors
- ETL pipeline (extract, transform, load)
- Job scheduler (parallel APIs, every 10s)
- Alerting and email notifications
- Database schema bootstrap
- Modular, extensible Python codebase
