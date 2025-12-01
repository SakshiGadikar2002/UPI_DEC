# ETL Tool - Real-Time Data Processing Platform

A comprehensive Extract, Transform, Load (ETL) tool designed for real-time data ingestion, processing, and visualization. This platform supports multiple data sources including WebSocket streams, REST APIs, and file uploads, with PostgreSQL as the primary data storage backend.

## 🚀 Features

### Core Capabilities
- **Real-Time Data Streaming**: WebSocket connections to OKX, Binance, and custom endpoints
- **REST API Integration**: Polling-based data extraction from any REST API
- **File Processing**: CSV and JSON file upload and processing
- **PostgreSQL Storage**: Automatic data persistence with optimized indexing
- **Real-Time Dashboard**: Live charts, metrics, and data visualization
- **Data Transformation**: Flexible transformation pipelines
- **Encrypted Credentials**: Secure storage of API keys and authentication tokens

### Supported Data Sources
- **WebSocket Streams**: OKX, Binance, Custom WebSocket endpoints
- **REST APIs**: Any HTTP/HTTPS endpoint with configurable authentication
- **File Uploads**: CSV, JSON formats

### Real-Time Features
- Live price tracking for 20 major cryptocurrencies
- Real-time dashboard with charts and metrics
- Global list view with live updates
- Comparison view for multiple instruments
- Performance metrics (latency, throughput, scalability)

## 📁 Project Structure

```
etl-tool/
├── backend/              # FastAPI backend server
│   ├── main.py          # Main API application
│   ├── database.py      # PostgreSQL connection and schema
│   ├── connectors/      # Data source connectors
│   ├── etl/            # ETL pipeline components
│   ├── models/         # Pydantic data models
│   ├── services/       # Business logic services
│   └── requirements.txt # Python dependencies
├── frontend/            # React frontend application
│   ├── src/
│   │   ├── components/  # React components
│   │   ├── utils/      # Utility functions
│   │   └── App.jsx     # Main application
│   └── package.json    # Node.js dependencies
└── README.md           # This file
```

## 🛠️ Technology Stack

### Backend
- **Framework**: FastAPI (Python 3.8+)
- **Database**: PostgreSQL 17+
- **Async Library**: asyncpg, asyncio
- **WebSocket**: WebSockets, FastAPI WebSocket
- **Encryption**: cryptography
- **HTTP Client**: requests, aiohttp

### Frontend
- **Framework**: React 18+
- **Build Tool**: Vite
- **Charts**: Recharts
- **WebSocket Client**: socket.io-client
- **Styling**: CSS3 with modern design

## 🚦 Quick Start

### Prerequisites
- Python 3.8 or higher
- Node.js 16+ and npm
- PostgreSQL 17+ installed and running
- Git (optional)

### 1. Clone the Repository
```bash
git clone <repository-url>
cd etl-tool
```

### 2. Backend Setup

```bash
cd backend

# Install Python dependencies
pip install -r requirements.txt

# Configure PostgreSQL password (see backend/POSTGRESQL_SETUP.md)
# Update database.py or set environment variable:
# Windows PowerShell: $env:POSTGRES_PASSWORD="your_password"
# Linux/Mac: export POSTGRES_PASSWORD="your_password"

# Start the backend server
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The backend will automatically:
- Connect to PostgreSQL
- Create the `etl_tool` database if it doesn't exist
- Create all required tables and indexes
- Start the API server on http://localhost:8000

### 3. Frontend Setup

```bash
cd frontend

# Install Node.js dependencies
npm install

# Start the development server
npm run dev
```

The frontend will be available at http://localhost:5173

### 4. Verify Installation

1. **Backend Health Check**: Visit http://localhost:8000/docs (FastAPI Swagger UI)
2. **PostgreSQL Status**: Visit http://localhost:8000/api/postgres/status
3. **Frontend**: Open http://localhost:5173 in your browser

## 📚 Documentation

### Main Documentation Files
- **[Backend Documentation](./backend/backend.md)** - Complete backend technical documentation
- **[Frontend Documentation](./frontend/frontend.md)** - Complete frontend technical documentation
- **[PostgreSQL Setup Guide](./backend/POSTGRESQL_SETUP.md)** - Database setup and configuration
- **[Quick Start Guide](./backend/QUICK_START.md)** - Quick setup instructions
- **[Troubleshooting Guide](./backend/TROUBLESHOOTING.md)** - Common issues and solutions

### API Documentation
- **Interactive API Docs**: http://localhost:8000/docs (Swagger UI)
- **ReDoc**: http://localhost:8000/redoc

## 🔌 API Endpoints

### WebSocket Data
- `POST /api/websocket/save` - Save individual WebSocket message
- `POST /api/websocket/save-batch` - Save batch of messages
- `GET /api/websocket/data` - Retrieve WebSocket data with pagination
- `GET /api/websocket/data/count` - Get total message count

### Connector Management
- `POST /api/connectors` - Create new API connector
- `GET /api/connectors` - List all connectors
- `GET /api/connectors/{id}` - Get connector details
- `PUT /api/connectors/{id}` - Update connector
- `DELETE /api/connectors/{id}` - Delete connector
- `POST /api/connectors/{id}/start` - Start connector
- `POST /api/connectors/{id}/stop` - Stop connector
- `GET /api/connectors/{id}/status` - Get connector status
- `GET /api/connectors/{id}/data` - Get connector data

### Database
- `GET /api/postgres/status` - Check PostgreSQL connection status

### Real-Time WebSocket
- `WebSocket /api/realtime` - Real-time data updates to frontend
- `POST /api/realtime/test` - Test WebSocket broadcast

## 🗄️ Database Schema

### Tables
- **websocket_messages**: Individual real-time WebSocket messages
- **websocket_batches**: Batched messages with metrics
- **api_connectors**: API connector configurations
- **connector_status**: Connector runtime status
- **api_connector_data**: Data from API connectors

See [PostgreSQL Setup Guide](./backend/POSTGRESQL_SETUP.md) for detailed schema information.

## 🎯 Use Cases

### 1. Real-Time Cryptocurrency Tracking
- Connect to OKX or Binance WebSocket streams
- Track 20 major cryptocurrencies in real-time
- View live dashboard with charts and metrics
- Compare multiple instruments side-by-side

### 2. API Data Ingestion
- Create connectors for any REST API
- Configure authentication (API Key, HMAC, Bearer Token, Basic Auth)
- Set polling intervals for continuous data collection
- Store all responses in PostgreSQL

### 3. File Data Processing
- Upload CSV or JSON files
- Transform data using built-in transformations
- Export processed data
- View results in tabular format

## 🔒 Security Features

- **Encrypted Credentials**: All API keys and secrets are encrypted using AES-256
- **Secure Headers**: Custom headers support for authentication
- **CORS Protection**: Configured CORS middleware
- **Input Validation**: Pydantic models for data validation

## 📊 Performance

- **Connection Pooling**: PostgreSQL connection pool (5-20 connections)
- **Batch Processing**: Automatic batching for high-throughput streams
- **Indexed Queries**: Optimized database indexes for fast queries
- **Real-Time Updates**: WebSocket-based real-time UI updates
- **Efficient Memory Usage**: Message buffering and cleanup

## 🧪 Testing

### Backend Tests
```bash
cd backend
python test_postgres_connection.py  # Test PostgreSQL connection
python verify_setup.py              # Verify complete setup
```

### Frontend Tests
```bash
cd frontend
npm test  # Run tests (if configured)
```

## 🐛 Troubleshooting

See [Troubleshooting Guide](./backend/TROUBLESHOOTING.md) for common issues and solutions.

### Common Issues
1. **PostgreSQL Connection Failed**: Check password and service status
2. **Port Already in Use**: Change port in uvicorn command
3. **CORS Errors**: Verify frontend URL in CORS middleware
4. **WebSocket Connection Failed**: Check backend is running and accessible

## 📝 Development

### Backend Development
```bash
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend Development
```bash
cd frontend
npm run dev
```

### Code Style
- Backend: Follow PEP 8 Python style guide
- Frontend: Follow React best practices and ESLint rules

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📄 License

[Add your license information here]

## 👥 Authors

[Add author information here]

## 🙏 Acknowledgments

- FastAPI for the excellent async framework
- React and Vite for the modern frontend stack
- PostgreSQL for reliable data storage
- Recharts for beautiful data visualization

## 📞 Support

For issues, questions, or contributions:
- Open an issue on GitHub
- Check the troubleshooting guide
- Review the detailed documentation in backend/ and frontend/ folders

---

**Last Updated**: 2024
**Version**: 1.0.0

