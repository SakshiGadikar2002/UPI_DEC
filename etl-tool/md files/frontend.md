# Frontend Overview

## Main Files
- `index.html`: Main HTML entry point.
- `src/main.jsx`: React app entry, renders `<App />`.
- `src/App.jsx`: Main React component, routes and layout.
- `src/components/`: UI components (APISection, DataDisplay, PipelineViewer, RealtimeStream, etc).
- `src/utils/`: Utility scripts for backend checks, websocket, downloads, etc.
- `package.json`: Frontend dependencies (React, Recharts, Socket.io, etc).
- `vite.config.js`: Vite configuration, dev server, API proxy.

## How to Run
```bash
cd frontend
npm install
npm run dev -- --host --port 5173
```

## Environment Variables
Create `frontend/.env`:
```
VITE_API_BASE=http://localhost:8000
```

## Features
- React + Vite UI
- Real-time streaming charts
- API configuration and quick connect
- ETL pipeline viewer
- Data download (CSV, JSON)
- Responsive, modern dashboard
