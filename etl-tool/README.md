# ETL Tool - Real-Time Data Processing Platform

A comprehensive Extract, Transform, Load (ETL) tool designed for real-time data ingestion, processing, and visualization. This platform supports multiple data sources including WebSocket streams, REST APIs, and file uploads, with PostgreSQL as the primary data storage backend.

## 🚀 Features

### Core Capabilities
- **Real-Time Data Streaming**: WebSocket connections to OKX, Binance, and custom endpoints
- **REST API Integration**: Automated polling of multiple crypto APIs with parallel execution
- **Job Scheduling**: Scheduled execution of non-realtime APIs every 10 seconds
- **File Processing**: CSV and JSON file upload and processing
- **PostgreSQL Storage**: Automatic data persistence with optimized indexing
- **Real-Time Dashboard**: Live charts, metrics, and data visualization
- **Data Transformation**: Flexible transformation pipelines
- **Encrypted Credentials**: Secure storage of API keys and authentication tokens

## 📚 Documentation

- **[BACKEND.md](./BACKEND.md)** - Backend API documentation and architecture
- **[DATABASE.md](./DATABASE.md)** - Database schema and PostgreSQL setup
- **[JOB_SCHEDULING.md](./JOB_SCHEDULING.md)** - Job scheduler and API polling
- **[WEBSOCKET_REALTIME.md](./WEBSOCKET_REALTIME.md)** - WebSocket real-time APIs
- **[ADD_CUSTOM_APIS.md](./backend/ADD_CUSTOM_APIS.md)** - Guide for custom APIs
- **[FRONTEND.md](./frontend/FRONTEND.md)** - Frontend documentation

## 🚀 Quick Start

```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000

# Frontend (in another terminal)
cd frontend
npm install
npm run dev
```

Visit http://localhost:5173 (frontend) and http://localhost:8000/docs (API docs)

## 🛠️ Technology Stack

- **Backend**: FastAPI, PostgreSQL, APScheduler
- **Frontend**: React 18, Vite, CSS3
- **Async**: asyncio, asyncpg, ThreadPoolExecutor
- **WebSocket**: Real-time data streaming

## 🔑 Key Features

- ✅ 8 APIs executing in parallel every 10 seconds
- ✅ Real-time WebSocket streaming from Binance/OKX
- ✅ File upload and processing (CSV, JSON)
- ✅ Encrypted API key storage
- ✅ Full PostgreSQL schema with indexing
- ✅ Interactive Swagger API docs
- ✅ Live dashboard with charts and metrics

## 📞 For Help

Refer to the documentation files in the project root for detailed information about each component.

---

**Last Updated**: December 8, 2025 | **Version**: 1.0.0

