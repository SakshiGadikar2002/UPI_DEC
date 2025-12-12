# ETL Tool

Modern ETL playground with scheduled REST fetchers (8 parallel APIs), real-time streaming connectors, alerting, and a React/Vite frontend.

## Project layout
- `backend/` FastAPI app, job scheduler, connectors, ETL helpers, database access.
- `frontend/` React + Vite UI.
- `backend/job_scheduler/` recurring jobs (non-realtime APIs).
- `backend/connectors/` REST/WebSocket connectors.
- `backend/etl/` extract/transform/load helpers for ad‑hoc jobs.
- `backend/database.py` Postgres pool + schema bootstrap + pipeline helpers.

## Prerequisites
- Python 3.10+
- Node 18+
- PostgreSQL 13+

## Backend quick start
```bash
cd backend
python -m venv .venv
. .venv/Scripts/activate  # Windows PowerShell: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Set env (example)
set POSTGRES_HOST=localhost
set POSTGRES_PORT=5432
set POSTGRES_USER=postgres
set POSTGRES_PASSWORD=postgres
set POSTGRES_DB=etl_tool

# Run API
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## Frontend quick start
```bash
cd frontend
npm install
npm run dev -- --host --port 5173
```

Set `VITE_API_BASE` in a `.env` in `frontend/` (e.g. `VITE_API_BASE=http://localhost:8000`).

## Scheduled APIs (JobScheduler)
- 8 REST endpoints run in parallel every 10 seconds (non-realtime).
- Results are stored in `api_connector_data` / `api_connector_items`.
- Pipeline runs/steps are tracked in `pipeline_runs` / `pipeline_steps`.

## Key endpoints
- `GET /api/etl/active` — active scheduler APIs and latest stats.
- `GET /api/etl/pipeline/{connector_id}` — ETL pipeline view + recent activity.
- `GET /api/pipeline` — list pipelines (falls back to connectors if no runs yet).
- `GET /api/connectors/{connector_id}/data` — latest data rows for a connector.

## Pipeline viewer expectations
- Steps tracked as `extract`, `clean`, `transform`, `load`.
- Data and step history come from existing tables only (no new tables created).

## Troubleshooting
- Ensure PostgreSQL is reachable with provided env vars.
- If no pipelines appear, confirm the backend is running and the scheduler is logging every 10s.
- Frontend errors about `apiBase` usually mean `VITE_API_BASE` is missing or backend not reachable.

