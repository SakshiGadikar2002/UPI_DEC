# ETL Tool - Real-Time Data Processing Platform

A comprehensive Extract, Transform, Load (ETL) tool designed for real-time data ingestion, processing, and visualization. This platform supports multiple data sources including WebSocket streams, REST APIs, and file uploads, with PostgreSQL as the primary data storage backend.

## 🚀 Features

### Core Capabilities
- **Real-Time Data Streaming**: WebSocket connections to OKX, Binance, and custom endpoints
- **REST API Integration**: Automated polling of 8 crypto APIs with parallel execution
- **Dual Data Storage**: 
  - **Aggregate Data**: Complete API responses stored as JSON blobs
  - **Granular Data**: Individual items from API responses (100-1000+ rows per call)
- **Job Scheduling**: Scheduled execution of APIs every 10 seconds
- **File Processing**: CSV and JSON file upload and processing
- **PostgreSQL Storage**: Automatic data persistence with optimized indexing (6 tables, 5+ indexes)
- **Real-Time Dashboard**: Live charts, metrics, and data visualization
- **Data Transformation**: Flexible transformation pipelines
- **Encrypted Credentials**: Secure storage of API keys and authentication tokens

## 📊 Data Volume

With dual storage strategy:
- **Aggregate Table**: ~8 rows per 10 seconds (1 per API)
- **Granular Table**: ~3,000+ rows per 10 seconds (100-1000+ per API)
- **Total**: 3,000+ individual data points queryable every 10 seconds

Data sources include crypto prices, market caps, volumes, trading pairs, and more from:
- Binance (3 endpoints)
- CoinGecko (3 endpoints) 
- CryptoCompare (2 endpoints)

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
- ✅ **NEW**: Granular data extraction - 3,000+ individual items per 10 seconds
- ✅ Dual storage strategy (aggregate + granular)
- ✅ Real-time WebSocket streaming from Binance/OKX
- ✅ File upload and processing (CSV, JSON)
- ✅ Encrypted API key storage
- ✅ Full PostgreSQL schema with 6 tables and 5+ indexes
- ✅ Interactive Swagger API docs
- ✅ Live dashboard with charts and metrics
- ✅ 100% queryable granular data (not just JSON blobs)

## 📞 For Help

Refer to the documentation files in the project root for detailed information about each component.

---

**Last Updated**: December 8, 2025 | **Version**: 1.0.0

