# ETL Tool Quickstart

## 1) Clone & prerequisites
- Python 3.10+
- Node 18+
- PostgreSQL 13+

## 2) Backend setup
```bash
cd backend
python -m venv .venv
. .venv/Scripts/activate          # Windows PowerShell: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Environment (set in shell or .env):
```
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=etl_tool
```

Run API:
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## 3) Frontend setup
```bash
cd frontend
npm install
npm run dev -- --host --port 5173
```

Create `frontend/.env`:
```
VITE_API_BASE=http://localhost:8000
```

## 4) What runs automatically
- JobScheduler: 8 REST APIs, parallel, every 10s.
- Data stored in `api_connector_data` / `api_connector_items`.
- Pipeline tracked in `pipeline_runs` / `pipeline_steps` (steps: extract, clean, transform, load).

## 5) Key endpoints
- `GET /api/etl/active` — active scheduler APIs and latest stats.
- `GET /api/etl/pipeline/{connector_id}` — ETL pipeline view + recent activity + latest data.
- `GET /api/pipeline` — list pipelines (falls back to connectors if no runs yet).
- `GET /api/connectors/{connector_id}/data` — fetch rows for a connector.

## 6) Common issues
- No pipelines showing: ensure backend running, DB reachable, and scheduler logs appear every 10s.
- `apiBase is not defined`: set `VITE_API_BASE` and restart frontend dev server.
- Stale pipeline rows: wait for a fresh run (10s) to populate new steps; tables are existing only, no new schema required.

