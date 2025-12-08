from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, UploadFile, File, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any, Set
import uvicorn
from datetime import datetime
import requests
import json
from contextlib import asynccontextmanager
import uuid
import asyncio
import logging
import os
from pathlib import Path
import pandas as pd
import shutil
import time

from etl.extractor import Extractor
from etl.transformer import Transformer
from etl.loader import Loader
from etl.job_manager import JobManager
from database import connect_to_postgres, close_postgres_connection, get_pool
from models.websocket_data import WebSocketMessage, WebSocketBatch
from models.connector import (
    ConnectorCreate, ConnectorUpdate, ConnectorResponse, 
    ConnectorStatusResponse, AuthType, ConnectorStatus
)
from services.encryption import get_encryption_service
from services.connector_manager import get_connector_manager
from services.message_processor import MessageProcessor
from job_scheduler import start_job_scheduler, stop_job_scheduler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global job scheduler reference
_job_scheduler = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Connect to PostgreSQL
    await connect_to_postgres()
    
    # Initialize scheduled connector records
    try:
        from database import initialize_scheduled_connectors
        await initialize_scheduled_connectors()
    except Exception as e:
        logger.warning(f"[STARTUP] Could not initialize scheduled connectors: {e}")
    
    # Schedule job scheduler startup to run after the app is ready
    # This gives us access to the save_to_database function
    def start_scheduler_later():
        try:
            loop = asyncio.get_event_loop()
            start_job_scheduler(loop, save_to_database)
            logger.info("[STARTUP] Job scheduler initialized and running")
        except Exception as e:
            logger.error(f"[STARTUP] Failed to start job scheduler: {e}")
            import traceback
            traceback.print_exc()
    
    # Run scheduler start in the event loop after a brief delay to ensure app is ready
    asyncio.get_event_loop().call_soon(start_scheduler_later)
    
    yield
    
    # Shutdown: Stop job scheduler and close PostgreSQL connection
    try:
        stop_job_scheduler()
        logger.info("[SHUTDOWN] Job scheduler stopped successfully")
    except Exception as e:
        logger.error(f"[SHUTDOWN] Error stopping job scheduler: {e}")
    
    await close_postgres_connection()


app = FastAPI(title="ETL Tool API", version="1.0.0", lifespan=lifespan)

# CORS middleware - allow all origins since we're serving from same port
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins since frontend is served from same port
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Get the path to frontend dist directory
# Backend is in etl-tool/backend/, frontend dist is in etl-tool/frontend/dist/
BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIST = BASE_DIR / "frontend" / "dist"

# Create uploads directory
UPLOADS_DIR = BASE_DIR / "backend" / "uploads"
UPLOADS_DIR.mkdir(exist_ok=True)

# Create processed directory
PROCESSED_DIR = BASE_DIR / "backend" / "processed"
PROCESSED_DIR.mkdir(exist_ok=True)

# Mount static files (CSS, JS, images, etc.)
if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST / "assets")), name="assets")
    logger.info(f"Static files mounted from: {FRONTEND_DIST}")
else:
    logger.warning(f"Frontend dist directory not found at: {FRONTEND_DIST}")

# Initialize job manager
job_manager = JobManager()

# Initialize encryption service
encryption_service = get_encryption_service()

# WebSocket connection manager for real-time UI updates
class ConnectionManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(f"WebSocket client connected. Total connections: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
        logger.info(f"WebSocket client disconnected. Total connections: {len(self.active_connections)}")
    
    async def broadcast(self, message: dict):
        """Broadcast message to all connected clients"""
        if not self.active_connections:
            logger.debug("No active WebSocket connections to broadcast to")
            return
        
        logger.info(f"Broadcasting to {len(self.active_connections)} WebSocket client(s)")
        disconnected = set()
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
                logger.debug(f"Message broadcasted successfully to client")
            except Exception as e:
                logger.error(f"Error broadcasting to client: {e}")
                disconnected.add(connection)
        
        # Remove disconnected clients
        for conn in disconnected:
            self.disconnect(conn)

connection_manager = ConnectionManager()

# Initialize message processor with callbacks
async def save_to_database(message: dict):
    """Save processed message to database"""
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            # Extract fields
            connector_id = message.get("connector_id", "unknown")
            exchange = message.get("exchange", "custom")
            instrument = message.get("instrument")
            price = message.get("price")
            data = message.get("data", {})
            message_type = message.get("message_type", "api_response")
            timestamp_str = message.get("timestamp")
            raw_response = message.get("raw_response")
            status_code = message.get("status_code")
            response_time_ms = message.get("response_time_ms")
            
            # Parse timestamp
            if timestamp_str:
                try:
                    timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                except:
                    timestamp = datetime.utcnow()
            else:
                timestamp = datetime.utcnow()
            
            # Generate source_id and session_id
            import hashlib
            import uuid
            source_id = hashlib.md5(f"{connector_id}_{timestamp}_{json.dumps(data)}".encode()).hexdigest()[:16]
            session_id = message.get("session_id", str(uuid.uuid4()))
            
            # Insert into api_connector_data table (dedicated table for API connector data)
            # Try with foreign key constraint first; if fails (scheduled APIs), insert without it
            try:
                inserted_id = await conn.fetchval("""
                    INSERT INTO api_connector_data (
                        connector_id, timestamp, exchange, instrument, price, data, 
                        message_type, raw_response, status_code, response_time_ms, source_id, session_id
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                    RETURNING id
                """, 
                    connector_id, timestamp, exchange, instrument, price, 
                    json.dumps(data), message_type, 
                    json.dumps(raw_response) if raw_response else None,
                    status_code, response_time_ms, source_id, session_id
                )
            except Exception as fk_error:
                # If foreign key constraint fails (e.g., for scheduled APIs), try inserting with NULL connector_id reference
                # This allows scheduled API data to be stored without requiring a connector record
                if "foreign key constraint" in str(fk_error).lower():
                    logger.debug(f"[OK] Inserting scheduled API data (bypassing FK constraint): {connector_id}")
                    try:
                        # Insert directly without FK constraint by using a special marker
                        inserted_id = await conn.fetchval("""
                            INSERT INTO api_connector_data (
                                connector_id, timestamp, exchange, instrument, price, data, 
                                message_type, raw_response, status_code, response_time_ms, source_id, session_id
                            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                            RETURNING id
                        """, 
                            f"scheduled_{connector_id}", timestamp, exchange, instrument, price, 
                            json.dumps(data), message_type, 
                            json.dumps(raw_response) if raw_response else None,
                            status_code, response_time_ms, source_id, session_id
                        )
                        connector_id = f"scheduled_{connector_id}"
                    except Exception as retry_error:
                        logger.error(f"[ERROR] Failed to insert scheduled API data even with marker: {retry_error}")
                        raise
                else:
                    raise
            
            # Also insert into websocket_messages for backward compatibility
            await conn.execute("""
                INSERT INTO websocket_messages (
                    timestamp, exchange, instrument, price, data, message_type
                ) VALUES ($1, $2, $3, $4, $5, $6)
            """, timestamp, exchange, instrument, price, json.dumps(data), message_type)
            
            logger.info(f"[OK] Saved API connector data to database: id={inserted_id}, source_id={source_id}, connector_id={connector_id}")
            
            # Return the saved record
            return {
                "id": inserted_id,
                "source_id": source_id,
                "session_id": session_id,
                "connector_id": connector_id,
                "timestamp": timestamp.isoformat(),
                "exchange": exchange,
                "instrument": instrument,
                "price": price,
                "data": data,
                "message_type": message_type,
                "raw_response": raw_response,
                "status_code": status_code,
                "response_time_ms": response_time_ms
            }
    except Exception as e:
        logger.error(f"Error saving to database: {e}")
        import traceback
        traceback.print_exc()
        return None

async def broadcast_to_websocket(message: dict):
    """Save to database first, then broadcast message to WebSocket clients with database info"""
    try:
        # Save to database first
        saved_record = await save_to_database(message)
        
        if saved_record:
            # Include database ID, source_id, and session_id in broadcast
            broadcast_message = {
                **message,
                "id": saved_record["id"],
                "source_id": saved_record["source_id"],
                "session_id": saved_record["session_id"],
                "db_timestamp": saved_record["timestamp"],
                "type": "data_update"  # Mark as data update for frontend
            }
            
            # Broadcast to all connected WebSocket clients
            await connection_manager.broadcast(broadcast_message)
            logger.info(f"[BROADCAST] Broadcasting message: id={saved_record['id']}, source_id={saved_record['source_id']}, connector_id={saved_record['connector_id']}")
        else:
            # If save failed, still try to broadcast the original message
            await connection_manager.broadcast(message)
            logger.warning(f"[WARNING] Broadcast without database save: connector_id={message.get('connector_id')}")
    except Exception as e:
        logger.error(f"Error in broadcast_to_websocket: {e}")
        import traceback
        traceback.print_exc()
        import traceback
        traceback.print_exc()

message_processor = MessageProcessor(
    db_callback=save_to_database,
    websocket_callback=broadcast_to_websocket
)

# Initialize connector manager with message processor
connector_manager = get_connector_manager(message_processor)


# ==================== Job Scheduler Setup ====================
@app.on_event("startup")
async def startup_job_scheduler():
    """Start job scheduler on application startup."""
    global _job_scheduler
    try:
        loop = asyncio.get_event_loop()
        _job_scheduler = start_job_scheduler(loop, save_to_database)
        logger.info("[STARTUP] Job scheduler initialized and running")
    except Exception as e:
        logger.error(f"[STARTUP] Failed to start job scheduler: {e}")
        import traceback
        traceback.print_exc()


@app.on_event("shutdown")
async def shutdown_job_scheduler():
    """Stop job scheduler on application shutdown."""
    try:
        stop_job_scheduler()
        logger.info("[SHUTDOWN] Job scheduler stopped successfully")
    except Exception as e:
        logger.error(f"[SHUTDOWN] Error stopping job scheduler: {e}")
# ================================================================


class ETLJobRequest(BaseModel):
    name: str
    source_type: str  # "csv", "json", "api", "database"
    source_config: Dict[str, Any]
    destination_type: str  # "csv", "json", "database"
    destination_config: Dict[str, Any]
    transformations: Optional[List[Dict[str, Any]]] = []


class JobStatusResponse(BaseModel):
    job_id: str
    name: str
    status: str
    progress: float
    created_at: str
    updated_at: str
    error: Optional[str] = None


@app.get("/")
async def root():
    """Serve frontend index.html or return API info"""
    # If frontend dist exists, serve it; otherwise return API info
    index_path = FRONTEND_DIST / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return {"message": "ETL Tool API", "version": "1.0.0"}


@app.post("/api/jobs", response_model=JobStatusResponse)
async def create_job(job_request: ETLJobRequest):
    """Create a new ETL job"""
    try:
        job = job_manager.create_job(
            name=job_request.name,
            source_type=job_request.source_type,
            source_config=job_request.source_config,
            destination_type=job_request.destination_type,
            destination_config=job_request.destination_config,
            transformations=job_request.transformations
        )
        return JobStatusResponse(
            job_id=job["job_id"],
            name=job["name"],
            status=job["status"],
            progress=job["progress"],
            created_at=job["created_at"],
            updated_at=job["updated_at"]
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/jobs", response_model=List[JobStatusResponse])
async def get_jobs():
    """Get all ETL jobs"""
    jobs = job_manager.get_all_jobs()
    return [JobStatusResponse(**job) for job in jobs]


@app.get("/api/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job(job_id: str):
    """Get a specific ETL job"""
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobStatusResponse(**job)


@app.post("/api/jobs/{job_id}/run")
async def run_job(job_id: str):
    """Run an ETL job"""
    try:
        job_manager.run_job(job_id)
        return {"message": "Job started", "job_id": job_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/jobs/{job_id}")
async def delete_job(job_id: str):
    """Delete an ETL job"""
    try:
        job_manager.delete_job(job_id)
        return {"message": "Job deleted", "job_id": job_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/exchanges/okx/instruments")
async def get_okx_instruments():
    """Fetch all available trading instruments from OKX"""
    try:
        response = requests.get(
            "https://www.okx.com/api/v5/public/instruments",
            params={"instType": "SPOT"},
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        
        if data.get("code") == "0" and data.get("data"):
            instruments = []
            for inst in data["data"]:
                instruments.append({
                    "instId": inst.get("instId"),
                    "baseCcy": inst.get("baseCcy"),
                    "quoteCcy": inst.get("quoteCcy"),
                    "displayName": f"{inst.get('baseCcy')}/{inst.get('quoteCcy')}"
                })
            instruments.sort(key=lambda x: (x["baseCcy"], x["quoteCcy"]))
            return {"instruments": instruments, "count": len(instruments)}
        else:
            raise HTTPException(status_code=500, detail="Failed to fetch OKX instruments")
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Error fetching OKX instruments: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


@app.get("/api/exchanges/binance/symbols")
async def get_binance_symbols():
    """Fetch all available trading symbols from Binance"""
    try:
        response = requests.get(
            "https://api.binance.com/api/v3/exchangeInfo",
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        
        if data.get("symbols"):
            symbols = []
            for symbol_info in data["symbols"]:
                if symbol_info.get("status") == "TRADING" and symbol_info.get("type") == "SPOT":
                    symbols.append({
                        "symbol": symbol_info.get("symbol"),
                        "baseAsset": symbol_info.get("baseAsset"),
                        "quoteAsset": symbol_info.get("quoteAsset"),
                        "displayName": f"{symbol_info.get('baseAsset')}/{symbol_info.get('quoteAsset')}"
                    })
            symbols.sort(key=lambda x: (x["baseAsset"], x["quoteAsset"]))
            return {"symbols": symbols, "count": len(symbols)}
        else:
            raise HTTPException(status_code=500, detail="Failed to fetch Binance symbols")
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Error fetching Binance symbols: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


# CoinGecko API Proxy Endpoints (to avoid CORS issues)
COINGECKO_API_BASE = "https://api.coingecko.com/api/v3"
# Rate limiting: track last request time
_last_coingecko_request = {"time": 0}
MIN_REQUEST_INTERVAL = 1.0  # Minimum 1 second between requests


@app.get("/api/crypto/global-stats")
async def get_global_crypto_stats():
    """Proxy endpoint to fetch global cryptocurrency market statistics from CoinGecko"""
    try:
        # Rate limiting: ensure minimum interval between requests
        current_time = time.time()
        time_since_last = current_time - _last_coingecko_request["time"]
        if time_since_last < MIN_REQUEST_INTERVAL:
            await asyncio.sleep(MIN_REQUEST_INTERVAL - time_since_last)
        
        _last_coingecko_request["time"] = time.time()
        
        response = requests.get(
            f"{COINGECKO_API_BASE}/global",
            timeout=15,
            headers={"Accept": "application/json"}
        )
        response.raise_for_status()
        data = response.json()
        return JSONResponse(content=data)
    except requests.exceptions.Timeout:
        raise HTTPException(status_code=504, detail="CoinGecko API timeout")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching global stats from CoinGecko: {e}")
        raise HTTPException(status_code=502, detail=f"Error fetching global stats: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error in global stats: {e}")
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


@app.get("/api/crypto/markets")
async def get_crypto_markets(
    ids: str = Query(..., description="Comma-separated list of coin IDs"),
    vs_currency: str = Query("usd", description="Target currency"),
    order: str = Query("market_cap_desc", description="Order by"),
    per_page: int = Query(20, description="Results per page"),
    page: int = Query(1, description="Page number"),
    sparkline: bool = Query(False, description="Include sparkline data"),
    price_change_percentage: Optional[str] = Query(None, description="Price change percentages")
):
    """Proxy endpoint to fetch cryptocurrency market data from CoinGecko"""
    try:
        # Rate limiting: ensure minimum interval between requests
        current_time = time.time()
        time_since_last = current_time - _last_coingecko_request["time"]
        if time_since_last < MIN_REQUEST_INTERVAL:
            await asyncio.sleep(MIN_REQUEST_INTERVAL - time_since_last)
        
        _last_coingecko_request["time"] = time.time()
        
        params = {
            "vs_currency": vs_currency,
            "ids": ids,
            "order": order,
            "per_page": per_page,
            "page": page,
            "sparkline": str(sparkline).lower()
        }
        
        if price_change_percentage:
            params["price_change_percentage"] = price_change_percentage
        
        response = requests.get(
            f"{COINGECKO_API_BASE}/coins/markets",
            params=params,
            timeout=15,
            headers={"Accept": "application/json"}
        )
        response.raise_for_status()
        data = response.json()
        return JSONResponse(content=data)
    except requests.exceptions.Timeout:
        raise HTTPException(status_code=504, detail="CoinGecko API timeout")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching markets from CoinGecko: {e}")
        raise HTTPException(status_code=502, detail=f"Error fetching markets: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error in markets: {e}")
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


# PostgreSQL WebSocket Data Endpoints
@app.post("/api/websocket/save")
async def save_websocket_message(message_data: Dict[str, Any]):
    """Save a single WebSocket message to PostgreSQL in real-time"""
    try:
        pool = get_pool()
        
        # Extract instrument and price from message data
        instrument = None
        price = None
        raw_data = message_data.get("data", {})
        
        # Helper function to extract price - enhanced recursive search
        def extract_price(data_obj, depth=0, max_depth=5):
            """Extract price from various data formats with recursive search"""
            if not data_obj or depth > max_depth:
                return None
            
            if isinstance(data_obj, dict):
                # Try different price field names first (most common cases)
                for price_field in ["px", "p", "last", "c", "price", "close", "lastPrice", "tradePrice"]:
                    if price_field in data_obj and data_obj[price_field] is not None:
                        try:
                            price_val = data_obj[price_field]
                            # Handle string prices
                            if isinstance(price_val, str):
                                price_val = price_val.strip()
                                if price_val and price_val != "null" and price_val != "None":
                                    return float(price_val)
                            # Handle numeric prices
                            elif isinstance(price_val, (int, float)):
                                return float(price_val)
                        except (ValueError, TypeError):
                            continue
                
                # If no direct price field, recursively search nested structures
                # Check "data" field (common in OKX, Binance stream format)
                if "data" in data_obj:
                    nested_price = extract_price(data_obj["data"], depth + 1, max_depth)
                    if nested_price is not None:
                        return nested_price
                
                # Recursively search all values in the dict
                for key, value in data_obj.items():
                    if key not in ["arg", "stream", "event", "op", "id"]:  # Skip metadata fields
                        nested_price = extract_price(value, depth + 1, max_depth)
                        if nested_price is not None:
                            return nested_price
                            
            elif isinstance(data_obj, list) and len(data_obj) > 0:
                # Check first element (most common case)
                nested_price = extract_price(data_obj[0], depth + 1, max_depth)
                if nested_price is not None:
                    return nested_price
                # If first element doesn't have price, try all elements
                for item in data_obj:
                    nested_price = extract_price(item, depth + 1, max_depth)
                    if nested_price is not None:
                        return nested_price
            
            return None
        
        # Helper function to extract instrument
        def extract_instrument(data_obj):
            """Extract instrument from various data formats"""
            if not data_obj:
                return None
            if isinstance(data_obj, dict):
                # OKX format
                if "arg" in data_obj and isinstance(data_obj["arg"], dict):
                    inst_id = data_obj["arg"].get("instId")
                    if inst_id:
                        return inst_id
                # Binance stream format
                if "stream" in data_obj:
                    stream = data_obj["stream"]
                    symbol = stream.split("@")[0].upper()
                    # Format as BTC-USDT if 6 chars, otherwise keep as is
                    if len(symbol) == 6:
                        return f"{symbol[:3]}-{symbol[3:]}"
                    return symbol
                # Binance direct format: { "e": "trade", "s": "BTCUSDT", ... }
                if "s" in data_obj:
                    symbol = data_obj["s"]
                    if len(symbol) == 6:
                        return f"{symbol[:3]}-{symbol[3:]}"
                    return symbol
                # OKX direct format in data array
                if "data" in data_obj:
                    if isinstance(data_obj["data"], list) and len(data_obj["data"]) > 0:
                        trade = data_obj["data"][0]
                        if "instId" in trade:
                            return trade["instId"]
                    elif isinstance(data_obj["data"], dict):
                        return extract_instrument(data_obj["data"])
            return None
        
        # Extract instrument and price
        instrument = extract_instrument(raw_data)
        price = extract_price(raw_data)
        
        # Special handling for OKX format: { "arg": {...}, "data": [...] }
        if not price and isinstance(raw_data, dict):
            if "arg" in raw_data and "data" in raw_data:
                # OKX format - check data array
                if isinstance(raw_data["data"], list) and len(raw_data["data"]) > 0:
                    for trade_item in raw_data["data"]:
                        if isinstance(trade_item, dict):
                            # Try to extract price from trade item
                            trade_price = extract_price(trade_item)
                            if trade_price is not None:
                                price = trade_price
                                break
                            # Also try direct field access
                            for price_field in ["px", "p", "last", "c", "price"]:
                                if price_field in trade_item and trade_item[price_field] is not None:
                                    try:
                                        price_val = trade_item[price_field]
                                        if isinstance(price_val, str):
                                            price_val = price_val.strip()
                                            if price_val and price_val != "null":
                                                price = float(price_val)
                                                break
                                        elif isinstance(price_val, (int, float)):
                                            price = float(price_val)
                                            break
                                    except (ValueError, TypeError):
                                        continue
                        if price is not None:
                            break
        
        # If still no instrument/price, try checking the root data structure
        if not instrument or not price:
            # Check if data is the actual trade data directly
            if isinstance(raw_data, dict):
                # Binance direct: { "e": "trade", "s": "BTCUSDT", "p": "50000" }
                if raw_data.get("e") == "trade" and raw_data.get("s"):
                    if not instrument:
                        symbol = raw_data["s"]
                        instrument = f"{symbol[:3]}-{symbol[3:]}" if len(symbol) == 6 else symbol
                    if not price and raw_data.get("p"):
                        try:
                            price = float(raw_data["p"])
                        except (ValueError, TypeError):
                            pass
                # Binance 24hrTicker: { "e": "24hrTicker", "s": "BTCUSDT", "c": "50000" }
                elif raw_data.get("e") == "24hrTicker" and raw_data.get("s"):
                    if not instrument:
                        symbol = raw_data["s"]
                        instrument = f"{symbol[:3]}-{symbol[3:]}" if len(symbol) == 6 else symbol
                    if not price and raw_data.get("c"):
                        try:
                            price = float(raw_data["c"])
                        except (ValueError, TypeError):
                            pass
                # OKX direct in data array
                if raw_data.get("data") and isinstance(raw_data["data"], list):
                    for trade in raw_data["data"]:
                        if isinstance(trade, dict):
                            if not instrument and trade.get("instId"):
                                instrument = trade["instId"]
                            if not price and trade.get("px"):
                                try:
                                    price = float(trade["px"])
                                except (ValueError, TypeError):
                                    pass
                        if instrument and price:
                            break
                # Check nested data structure (Binance stream wrapper)
                if not instrument and raw_data.get("data") and isinstance(raw_data["data"], dict):
                    nested_data = raw_data["data"]
                    if nested_data.get("s"):
                        symbol = nested_data["s"]
                        instrument = f"{symbol[:3]}-{symbol[3:]}" if len(symbol) == 6 else symbol
                    if not price and nested_data.get("p"):
                        try:
                            price = float(nested_data["p"])
                        except (ValueError, TypeError):
                            pass
                    if not price and nested_data.get("c"):
                        try:
                            price = float(nested_data["c"])
                        except (ValueError, TypeError):
                            pass
        
        # Prepare timestamp
        timestamp = datetime.utcnow() if not message_data.get("timestamp") else datetime.fromisoformat(message_data["timestamp"].replace('Z', '+00:00')) if isinstance(message_data.get("timestamp"), str) else message_data["timestamp"]
        
        # Use PostgreSQL INSERT with error handling
        try:
            async with pool.acquire() as conn:
                inserted_id = await conn.fetchval("""
                    INSERT INTO websocket_messages (
                        timestamp, exchange, instrument, price, data, message_type,
                        latency_ms, message_number, format, extract_time, transform_time,
                        load_time, total_time
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                    RETURNING id
                """,
                    timestamp,
                    message_data.get("exchange", "custom"),
                    instrument,
                    price,
                    json.dumps(raw_data),
                    message_data.get("type", "trade"),
                    message_data.get("totalTime") * 1000 if message_data.get("totalTime") else None,
                    message_data.get("messageNumber"),
                    message_data.get("format"),
                    message_data.get("extractTime"),
                    message_data.get("transformTime"),
                    message_data.get("loadTime"),
                    message_data.get("totalTime")
                )
            
            if price is None:
                print(f"[WARNING] Saved message to PostgreSQL: instrument={instrument}, price=None (price not found in message), id={inserted_id}")
            else:
                print(f"[OK] Saved message to PostgreSQL: instrument={instrument}, price={price}, id={inserted_id}")
            
            return {
                "message": "Message saved", 
                "id": str(inserted_id), 
                "success": True, 
                "instrument": instrument, 
                "price": price
            }
        except Exception as insert_error:
            print(f"[ERROR] Error inserting message to PostgreSQL: {insert_error}")
            import traceback
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=f"Error inserting message: {str(insert_error)}")
    except Exception as e:
        print(f"[ERROR] Error saving individual message: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error saving message: {str(e)}")


@app.post("/api/websocket/save-batch")
async def save_websocket_batch(batch: WebSocketBatch):
    """Save a batch of WebSocket messages to PostgreSQL - saves both batch and individual messages"""
    try:
        pool = get_pool()
        
        # Convert batch to dict and ensure timestamp is datetime
        batch_dict = batch.dict()
        timestamp = batch_dict.get("timestamp")
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        elif timestamp is None:
            timestamp = datetime.utcnow()
        
        messages = batch_dict.get("messages", [])
        exchange = batch_dict.get("exchange", "custom")
        
        async with pool.acquire() as conn:
            # Start a transaction
            async with conn.transaction():
                # 1. Save the batch metadata
                inserted_id = await conn.fetchval("""
                    INSERT INTO websocket_batches (
                        timestamp, exchange, total_messages, messages_per_second,
                        instruments, messages, metrics
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                    RETURNING id
                """,
                    timestamp,
                    exchange,
                    batch_dict.get("total_messages"),
                    batch_dict.get("messages_per_second"),
                    batch_dict.get("instruments", []),
                    json.dumps(messages),
                    json.dumps(batch_dict.get("metrics", {}))
                )
                
                # 2. Save each individual message to websocket_messages table
                saved_count = 0
                for msg in messages:
                    try:
                        # Extract instrument and price from message
                        instrument = None
                        price = None
                        raw_data = msg.get("data", {})
                        
                        # Extract instrument
                        if isinstance(raw_data, dict):
                            if "arg" in raw_data and isinstance(raw_data["arg"], dict):
                                instrument = raw_data["arg"].get("instId")
                            elif "stream" in raw_data:
                                symbol = raw_data["stream"].split("@")[0].upper()
                                if len(symbol) == 6:
                                    instrument = f"{symbol[:3]}-{symbol[3:]}"
                                else:
                                    instrument = symbol
                            elif "s" in raw_data:
                                symbol = raw_data["s"]
                                if len(symbol) == 6:
                                    instrument = f"{symbol[:3]}-{symbol[3:]}"
                                else:
                                    instrument = symbol
                        
                        # Extract price
                        def extract_price(data_obj, depth=0, max_depth=5):
                            if not data_obj or depth > max_depth:
                                return None
                            if isinstance(data_obj, dict):
                                for price_field in ["px", "p", "last", "c", "price", "close", "lastPrice", "tradePrice"]:
                                    if price_field in data_obj and data_obj[price_field] is not None:
                                        try:
                                            price_val = data_obj[price_field]
                                            if isinstance(price_val, str):
                                                price_val = price_val.strip()
                                                if price_val and price_val != "null" and price_val != "None":
                                                    return float(price_val)
                                            elif isinstance(price_val, (int, float)):
                                                return float(price_val)
                                        except (ValueError, TypeError):
                                            continue
                                if "data" in data_obj:
                                    nested_price = extract_price(data_obj["data"], depth + 1, max_depth)
                                    if nested_price is not None:
                                        return nested_price
                                for key, value in data_obj.items():
                                    if key not in ["arg", "stream", "event", "op", "id"]:
                                        nested_price = extract_price(value, depth + 1, max_depth)
                                        if nested_price is not None:
                                            return nested_price
                            elif isinstance(data_obj, list) and len(data_obj) > 0:
                                nested_price = extract_price(data_obj[0], depth + 1, max_depth)
                                if nested_price is not None:
                                    return nested_price
                            return None
                        
                        price = extract_price(raw_data)
                        
                        # Prepare message timestamp
                        msg_timestamp = msg.get("timestamp")
                        if isinstance(msg_timestamp, str):
                            msg_timestamp = datetime.fromisoformat(msg_timestamp.replace('Z', '+00:00'))
                        elif msg_timestamp is None:
                            msg_timestamp = timestamp
                        
                        # Insert individual message to websocket_messages table
                        # Note: Some messages might be saved twice (once individually, once in batch), but that's okay
                        await conn.execute("""
                            INSERT INTO websocket_messages (
                                timestamp, exchange, instrument, price, data, message_type,
                                latency_ms, message_number, format, extract_time, transform_time,
                                load_time, total_time
                            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                        """,
                            msg_timestamp,
                            exchange,
                            instrument,
                            price,
                            json.dumps(raw_data),
                            msg.get("message_type", "trade"),
                            msg.get("latency_ms"),
                            None,  # message_number not in batch messages
                            None,  # format not in batch messages
                            None,  # extract_time not in batch messages
                            None,  # transform_time not in batch messages
                            None,  # load_time not in batch messages
                            None   # total_time not in batch messages
                        )
                        saved_count += 1
                    except Exception as msg_error:
                        # Log but continue saving other messages
                        print(f"[WARNING] Error saving individual message in batch: {msg_error}")
                        continue
                
                print(f"[OK] Saved batch to PostgreSQL: {inserted_id} with {saved_count} individual messages")
        
        return {
            "message": "Batch saved", 
            "id": str(inserted_id), 
            "success": True,
            "individual_messages_saved": saved_count
        }
    except Exception as e:
        print(f"[ERROR] Error saving batch: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error saving batch: {str(e)}")


@app.get("/api/postgres/status")
async def get_postgres_status():
    """Check PostgreSQL connection status and ensure database exists"""
    try:
        pool = get_pool()
        
        async with pool.acquire() as conn:
            # Test connection
            await conn.fetchval('SELECT 1')
            
            # Get table counts
            batches_count = await conn.fetchval('SELECT COUNT(*) FROM websocket_batches')
            messages_count = await conn.fetchval('SELECT COUNT(*) FROM websocket_messages')
            
            # Get database name
            db_name = await conn.fetchval('SELECT current_database()')
        
        return {
            "status": "connected", 
            "database": db_name,
            "tables": {
                "websocket_batches": batches_count,
                "websocket_messages": messages_count
            },
            "tables_list": ["websocket_batches", "websocket_messages"]
        }
    except Exception as e:
        print(f"[ERROR] PostgreSQL status check failed: {e}")
        return {"status": "disconnected", "error": str(e)}


@app.get("/api/websocket/data")
async def get_websocket_data(
    exchange: Optional[str] = None,
    instrument: Optional[str] = None,
    limit: int = 100,
    skip: int = 0,
    collection_type: str = "messages",  # "messages" or "batches"
    sort_by: str = "timestamp",  # Field to sort by
    sort_order: int = -1  # -1 for descending, 1 for ascending
):
    """Retrieve WebSocket data from PostgreSQL with pagination"""
    try:
        pool = get_pool()
        
        # Validate limit (max 100000 to prevent performance issues, but allow large queries)
        limit = min(max(1, limit), 100000)
        skip = max(0, skip)
        
        # Choose table
        if collection_type == "batches":
            table_name = "websocket_batches"
        else:
            table_name = "websocket_messages"
        
        # Build WHERE clause
        where_conditions = []
        params = []
        param_index = 1
        
        if exchange:
            where_conditions.append(f"exchange = ${param_index}")
            params.append(exchange)
            param_index += 1
        
        if instrument:
            where_conditions.append(f"instrument = ${param_index}")
            params.append(instrument)
            param_index += 1
        
        where_clause = "WHERE " + " AND ".join(where_conditions) if where_conditions else ""
        
        # Validate sort field
        valid_sort_fields = ["timestamp", "message_number", "price", "id"]
        sort_field = sort_by if sort_by in valid_sort_fields else "timestamp"
        sort_direction = "DESC" if sort_order < 0 else "ASC"
        
        # Get total count
        count_query = f"SELECT COUNT(*) FROM {table_name} {where_clause}"
        async with pool.acquire() as conn:
            total_count = await conn.fetchval(count_query, *params)
        
        # Build main query with proper parameterization
        query = f"""
            SELECT * FROM {table_name}
            {where_clause}
            ORDER BY {sort_field} {sort_direction}
            LIMIT ${param_index} OFFSET ${param_index + 1}
        """
        query_params = params + [limit, skip]
        
        async with pool.acquire() as conn:
            rows = await conn.fetch(query, *query_params)
        
        # Convert rows to dicts and serialize
        def serialize_row(row):
            """Serialize PostgreSQL row for JSON response"""
            result = {}
            for key, value in dict(row).items():
                if isinstance(value, datetime):
                    result[key] = value.isoformat()
                elif isinstance(value, dict):
                    result[key] = value
                elif isinstance(value, list):
                    result[key] = value
                else:
                    result[key] = value
            return result
        
        serialized_messages = [serialize_row(row) for row in rows]
        
        return {
            "messages": serialized_messages, 
            "count": len(serialized_messages),
            "total": total_count,
            "skip": skip,
            "limit": limit,
            "has_more": (skip + limit) < total_count,
            "collection": collection_type
        }
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"[ERROR] Error retrieving PostgreSQL data: {e}\n{error_details}")
        raise HTTPException(status_code=500, detail=f"Error retrieving data: {str(e)}")


@app.get("/api/websocket/data/count")
async def get_websocket_data_count(
    exchange: Optional[str] = None,
    instrument: Optional[str] = None,
    collection_type: str = "messages"
):
    """Get total count of WebSocket data in PostgreSQL"""
    try:
        pool = get_pool()
        
        # Choose table
        if collection_type == "batches":
            table_name = "websocket_batches"
        else:
            table_name = "websocket_messages"
        
        # Build WHERE clause
        where_conditions = []
        params = []
        param_index = 1
        
        if exchange:
            where_conditions.append(f"exchange = ${param_index}")
            params.append(exchange)
            param_index += 1
        
        if instrument:
            where_conditions.append(f"instrument = ${param_index}")
            params.append(instrument)
            param_index += 1
        
        where_clause = "WHERE " + " AND ".join(where_conditions) if where_conditions else ""
        
        query = f"SELECT COUNT(*) FROM {table_name} {where_clause}"
        
        async with pool.acquire() as conn:
            total_count = await conn.fetchval(query, *params)
        
        return {
            "total": total_count,
            "collection": collection_type,
            "exchange": exchange,
            "instrument": instrument
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting count: {str(e)}")


# ==================== Connector Management Endpoints ====================

@app.post("/api/connectors", response_model=ConnectorResponse)
async def create_connector(connector_data: ConnectorCreate):
    """Create a new API connector"""
    try:
        logger.info(f"📝 Creating connector: {connector_data.name} for URL: {connector_data.api_url}")
        logger.info(f"📝 Auth type: {connector_data.auth_type}")
        
        pool = get_pool()
        connector_id = f"conn_{uuid.uuid4().hex[:12]}"
        logger.info(f"📝 Generated connector_id: {connector_id}")
        
        # Detect protocol and exchange
        from connectors.connector_factory import ConnectorFactory
        protocol_type = ConnectorFactory.detect_protocol(connector_data.api_url)
        exchange_name = ConnectorFactory.detect_exchange(connector_data.api_url)
        logger.info(f"📝 Detected protocol: {protocol_type}, exchange: {exchange_name}")
        
        # Prepare credentials
        credentials = {}
        if connector_data.auth_type == AuthType.API_KEY:
            credentials["api_key"] = connector_data.api_key
            logger.info(f"📝 Added API key to credentials (length: {len(connector_data.api_key) if connector_data.api_key else 0})")
        elif connector_data.auth_type == AuthType.HMAC:
            credentials["api_key"] = connector_data.api_key
            credentials["api_secret"] = connector_data.api_secret
            logger.info(f"📝 Added HMAC credentials")
        elif connector_data.auth_type == AuthType.BEARER_TOKEN:
            credentials["bearer_token"] = connector_data.bearer_token
            logger.info(f"📝 Added Bearer token to credentials (length: {len(connector_data.bearer_token) if connector_data.bearer_token else 0})")
        elif connector_data.auth_type == AuthType.BASIC_AUTH:
            credentials["username"] = connector_data.username
            credentials["password"] = connector_data.password
            logger.info(f"📝 Added Basic Auth credentials (username: {connector_data.username})")
        
        logger.info(f"📝 Encrypting sensitive data...")
        # Encrypt sensitive data
        try:
            headers_encrypted = encryption_service.encrypt_dict(connector_data.headers or {}) if connector_data.headers else None
            logger.info(f"📝 Headers encrypted: {headers_encrypted is not None}")
        except Exception as e:
            logger.error(f"❌ Error encrypting headers: {e}")
            raise
        
        try:
            query_params_encrypted = encryption_service.encrypt_dict(connector_data.query_params or {}) if connector_data.query_params else None
            logger.info(f"📝 Query params encrypted: {query_params_encrypted is not None}")
        except Exception as e:
            logger.error(f"❌ Error encrypting query params: {e}")
            raise
        
        try:
            credentials_encrypted = encryption_service.encrypt_credentials(credentials) if credentials else None
            logger.info(f"📝 Credentials encrypted: {credentials_encrypted is not None}")
        except Exception as e:
            logger.error(f"❌ Error encrypting credentials: {e}")
            raise
        
        logger.info(f"📝 Saving to database...")
        # Save to database
        async with pool.acquire() as conn:
            inserted_id = await conn.fetchval("""
                INSERT INTO api_connectors (
                    connector_id, name, api_url, http_method, headers_encrypted,
                    query_params_encrypted, auth_type, credentials_encrypted,
                    status, polling_interval, protocol_type, exchange_name
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                RETURNING id
            """,
                connector_id, connector_data.name, connector_data.api_url,
                connector_data.http_method, headers_encrypted, query_params_encrypted,
                connector_data.auth_type.value, credentials_encrypted,
                ConnectorStatus.INACTIVE.value, connector_data.polling_interval,
                protocol_type, exchange_name
            )
            logger.info(f"📝 Saved to database with id: {inserted_id}")
            
            # Get created connector
            row = await conn.fetchrow(
                "SELECT * FROM api_connectors WHERE id = $1", inserted_id
            )
            logger.info(f"📝 Retrieved connector from database")
        
        # Create connector instance (outside database transaction to avoid blocking)
        logger.info(f"📝 Creating connector instance in memory...")
        try:
            connector = await connector_manager.create_connector(
                connector_id=connector_id,
                api_url=connector_data.api_url,
                http_method=connector_data.http_method,
                headers=connector_data.headers,
                query_params=connector_data.query_params,
                credentials=credentials,
                auth_type=connector_data.auth_type.value,
                polling_interval=connector_data.polling_interval
            )
            logger.info(f"✅ Connector instance created successfully")
        except Exception as e:
            logger.error(f"❌ Error creating connector instance: {e}")
            # Don't fail the whole request if connector instance creation fails
            # The connector is already saved in DB, instance can be created later
            import traceback
            traceback.print_exc()
        
        logger.info(f"✅ Connector created successfully: {connector_id}")
        return ConnectorResponse(
            id=row["id"],
            connector_id=row["connector_id"],
            name=row["name"],
            api_url=row["api_url"],
            http_method=row["http_method"],
            auth_type=row["auth_type"],
            status=row["status"],
            polling_interval=row["polling_interval"],
            protocol_type=row["protocol_type"],
            exchange_name=row["exchange_name"],
            created_at=row["created_at"],
            updated_at=row["updated_at"]
        )
    
    except Exception as e:
        logger.error(f"❌ Error creating connector: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/connectors", response_model=List[ConnectorResponse])
async def get_connectors():
    """Get all connectors"""
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM api_connectors ORDER BY created_at DESC")
        
        return [ConnectorResponse(**dict(row)) for row in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/connectors/{connector_id}", response_model=ConnectorResponse)
async def get_connector(connector_id: str):
    """Get a specific connector"""
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM api_connectors WHERE connector_id = $1", connector_id
            )
        
        if not row:
            raise HTTPException(status_code=404, detail="Connector not found")
        
        return ConnectorResponse(**dict(row))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/connectors/{connector_id}", response_model=ConnectorResponse)
async def update_connector(connector_id: str, connector_data: ConnectorUpdate):
    """Update a connector"""
    try:
        pool = get_pool()
        
        # Get existing connector
        async with pool.acquire() as conn:
            existing = await conn.fetchrow(
                "SELECT * FROM api_connectors WHERE connector_id = $1", connector_id
            )
            if not existing:
                raise HTTPException(status_code=404, detail="Connector not found")
            
            # Build update query
            updates = []
            params = []
            param_index = 1
            
            if connector_data.name is not None:
                updates.append(f"name = ${param_index}")
                params.append(connector_data.name)
                param_index += 1
            
            if connector_data.api_url is not None:
                updates.append(f"api_url = ${param_index}")
                params.append(connector_data.api_url)
                param_index += 1
            
            if connector_data.status is not None:
                updates.append(f"status = ${param_index}")
                params.append(connector_data.status.value)
                param_index += 1
            
            if connector_data.polling_interval is not None:
                updates.append(f"polling_interval = ${param_index}")
                params.append(connector_data.polling_interval)
                param_index += 1
            
            updates.append(f"updated_at = ${param_index}")
            params.append(datetime.utcnow())
            param_index += 1
            
            params.append(connector_id)
            
            if updates:
                await conn.execute(
                    f"UPDATE api_connectors SET {', '.join(updates)} WHERE connector_id = ${param_index}",
                    *params
                )
            
            # Get updated connector
            row = await conn.fetchrow(
                "SELECT * FROM api_connectors WHERE connector_id = $1", connector_id
            )
        
        return ConnectorResponse(**dict(row))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/connectors/{connector_id}")
async def delete_connector(connector_id: str):
    """Delete a connector"""
    try:
        await connector_manager.delete_connector(connector_id)
        
        pool = get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM api_connectors WHERE connector_id = $1", connector_id
            )
        
        return {"message": "Connector deleted", "connector_id": connector_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/connectors/{connector_id}/start")
async def start_connector(connector_id: str):
    """Start a connector"""
    try:
        # Load connector from database
        pool = get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM api_connectors WHERE connector_id = $1", connector_id
            )
            if not row:
                raise HTTPException(status_code=404, detail="Connector not found")
            
            # Decrypt credentials - handle None and empty strings
            headers_encrypted = row.get("headers_encrypted")
            query_params_encrypted = row.get("query_params_encrypted")
            credentials_encrypted = row.get("credentials_encrypted")
            
            try:
                headers = encryption_service.decrypt_dict(headers_encrypted) if headers_encrypted else {}
            except Exception as e:
                logger.warning(f"Failed to decrypt headers: {e}, using empty dict")
                headers = {}
            
            try:
                query_params = encryption_service.decrypt_dict(query_params_encrypted) if query_params_encrypted else {}
            except Exception as e:
                logger.warning(f"Failed to decrypt query_params: {e}, using empty dict")
                query_params = {}
            
            try:
                credentials = encryption_service.decrypt_credentials(credentials_encrypted) if credentials_encrypted else {}
            except Exception as e:
                logger.warning(f"Failed to decrypt credentials: {e}, using empty dict")
                credentials = {}
            
            # Create or get connector instance
            connector = await connector_manager.get_connector(connector_id)
            if not connector:
                connector = await connector_manager.create_connector(
                    connector_id=connector_id,
                    api_url=row["api_url"],
                    http_method=row["http_method"],
                    headers=headers,
                    query_params=query_params,
                    credentials=credentials,
                    auth_type=row["auth_type"],
                    polling_interval=row["polling_interval"]
                )
            
            # Start connector
            await connector_manager.start_connector(connector_id)
            
            return {"message": "Connector started", "connector_id": connector_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting connector: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/connectors/{connector_id}/stop")
async def stop_connector(connector_id: str):
    """Stop a connector"""
    try:
        await connector_manager.stop_connector(connector_id)
        return {"message": "Connector stopped", "connector_id": connector_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/connectors/{connector_id}/status", response_model=ConnectorStatusResponse)
async def get_connector_status(connector_id: str):
    """Get connector status"""
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM connector_status WHERE connector_id = $1", connector_id
            )
        
        if not row:
            raise HTTPException(status_code=404, detail="Connector status not found")
        
        return ConnectorStatusResponse(**dict(row))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Real-Time WebSocket Endpoint ====================

@app.post("/api/realtime/test")
async def test_websocket_broadcast():
    """Test endpoint to broadcast a test message to all WebSocket clients"""
    test_message = {
        "type": "test",
        "exchange": "test",
        "instrument": "TEST-USDT",
        "price": 100.50,
        "data": {"test": "data", "timestamp": datetime.utcnow().isoformat()},
        "message_type": "test",
        "timestamp": datetime.utcnow().isoformat(),
        "connector_id": "test"
    }
    await connection_manager.broadcast(test_message)
    return {"message": "Test message broadcasted", "clients": len(connection_manager.active_connections)}


@app.get("/api/connectors/{connector_id}/data")
async def get_connector_data(
    connector_id: str,
    limit: int = 100,
    skip: int = 0,
    sort_by: str = "timestamp",
    sort_order: int = -1
):
    """Get data for a specific connector from database - formatted for table display"""
    try:
        pool = get_pool()
        
        # Validate limit
        limit = min(max(1, limit), 10000)
        skip = max(0, skip)
        
        # Validate sort field
        valid_sort_fields = ["timestamp", "id", "price"]
        sort_field = sort_by if sort_by in valid_sort_fields else "timestamp"
        sort_direction = "DESC" if sort_order < 0 else "ASC"
        
        # Get total count
        async with pool.acquire() as conn:
            total_count = await conn.fetchval(
                "SELECT COUNT(*) FROM api_connector_data WHERE connector_id = $1",
                connector_id
            )
        
        # Get data
        query = f"""
            SELECT * FROM api_connector_data
            WHERE connector_id = $1
            ORDER BY {sort_field} {sort_direction}
            LIMIT $2 OFFSET $3
        """
        
        async with pool.acquire() as conn:
            rows = await conn.fetch(query, connector_id, limit, skip)
        
        # Format data for table display
        def format_row_for_table(row):
            row_dict = dict(row)
            
            # Parse JSONB fields
            data_field = row_dict.get("data")
            raw_response_field = row_dict.get("raw_response")
            
            # Parse data if it's a string
            if isinstance(data_field, str):
                try:
                    data_field = json.loads(data_field)
                except:
                    pass
            
            # Parse raw_response if it's a string
            if isinstance(raw_response_field, str):
                try:
                    raw_response_field = json.loads(raw_response_field)
                except:
                    pass
            
            # Format timestamp
            timestamp = row_dict.get("timestamp")
            if isinstance(timestamp, datetime):
                timestamp = timestamp.isoformat()
            
            # Create table-friendly format
            formatted = {
                "id": row_dict.get("id"),
                "source_id": row_dict.get("source_id") or str(row_dict.get("id", "")),
                "session_id": row_dict.get("session_id") or connector_id,
                "timestamp": timestamp,
                "connector_id": row_dict.get("connector_id") or connector_id,
                "exchange": row_dict.get("exchange") or "unknown",
                "instrument": row_dict.get("instrument") or "-",
                "price": row_dict.get("price"),
                "message_type": row_dict.get("message_type") or "api_response",
                "status_code": row_dict.get("status_code"),
                "response_time_ms": row_dict.get("response_time_ms"),
                "processed_data": data_field,  # The actual API response data
                "raw_data": raw_response_field if raw_response_field else data_field  # Raw response
            }
            
            return formatted
        
        serialized_data = [format_row_for_table(row) for row in rows]
        
        logger.info(f"Returning {len(serialized_data)} records for connector {connector_id} (total: {total_count})")
        
        return {
            "data": serialized_data,
            "count": len(serialized_data),
            "total": total_count,
            "skip": skip,
            "limit": limit,
            "has_more": (skip + limit) < total_count,
            "connector_id": connector_id
        }
    except Exception as e:
        logger.error(f"Error getting connector data: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.websocket("/api/realtime")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time data updates to UI"""
    await connection_manager.connect(websocket)
    try:
        # Send initial connection message
        await websocket.send_json({"type": "connected", "message": "WebSocket connected"})
        logger.info("WebSocket client connected and initial message sent")
        
        # Keep connection alive - use a task to handle incoming messages without blocking
        async def keep_alive():
            while True:
                try:
                    # Wait for any message from client (with timeout to keep connection alive)
                    data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                    logger.debug(f"Received message from client: {data}")
                except asyncio.TimeoutError:
                    # Send ping to keep connection alive
                    try:
                        await websocket.send_json({"type": "ping", "timestamp": datetime.utcnow().isoformat()})
                    except:
                        break
                except Exception:
                    break
        
        # Run keep_alive in background
        keep_alive_task = asyncio.create_task(keep_alive())
        
        try:
            await keep_alive_task
        except asyncio.CancelledError:
            pass
            
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected normally")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        connection_manager.disconnect(websocket)
        logger.info("WebSocket connection closed")


# File Upload and Processing Endpoints
@app.post("/api/files/upload")
async def upload_file(file: UploadFile = File(...)):
    """Upload a file (CSV, JSON, or XLSX)"""
    try:
        # Validate file type
        file_ext = file.filename.split('.')[-1].lower()
        if file_ext not in ['csv', 'json', 'xlsx', 'xls']:
            raise HTTPException(status_code=400, detail=f"Unsupported file type: {file_ext}. Supported types: CSV, JSON, XLSX")
        
        # Generate unique file ID
        file_id = str(uuid.uuid4())
        file_path = UPLOADS_DIR / f"{file_id}_{file.filename}"
        
        # Save uploaded file
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Determine source type
        source_type = 'xlsx' if file_ext in ['xlsx', 'xls'] else file_ext
        
        return {
            "file_id": file_id,
            "filename": file.filename,
            "file_path": str(file_path),
            "source_type": source_type,
            "transformations": []  # Default empty transformations
        }
    except Exception as e:
        logger.error(f"Error uploading file: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class ProcessFileRequest(BaseModel):
    file_id: str
    transformations: Optional[List[Dict[str, Any]]] = []


@app.post("/api/files/preview")
async def preview_file(request: Dict[str, str]):
    """Get preview of an uploaded file"""
    try:
        file_id = request.get("file_id")
        if not file_id:
            raise HTTPException(status_code=400, detail="file_id is required")
        
        # Find the uploaded file
        uploaded_files = list(UPLOADS_DIR.glob(f"{file_id}_*"))
        if not uploaded_files:
            raise HTTPException(status_code=404, detail="File not found")
        
        file_path = uploaded_files[0]
        file_ext = file_path.suffix.lower().replace('.', '')
        if not file_ext:
            # Try to get extension from filename
            file_ext = str(file_path).split('.')[-1].lower()
        source_type = 'xlsx' if file_ext in ['xlsx', 'xls'] else file_ext
        
        # Extract data
        df = Extractor.extract(source_type, {"file_path": str(file_path)})
        
        # Get preview (first 10 rows)
        preview = {
            "columns": df.columns.tolist(),
            "rows": df.head(10).to_dict(orient='records'),
            "totalRows": len(df),
            "totalColumns": len(df.columns)
        }
        
        return {"preview": preview}
    except Exception as e:
        logger.error(f"Error previewing file: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/files/process")
async def process_file(request: ProcessFileRequest):
    """Process an uploaded file through the ETL pipeline"""
    try:
        # Find the uploaded file
        uploaded_files = list(UPLOADS_DIR.glob(f"{request.file_id}_*"))
        if not uploaded_files:
            raise HTTPException(status_code=404, detail="File not found")
        
        file_path = uploaded_files[0]
        file_ext = file_path.suffix.lower().replace('.', '')
        if not file_ext:
            # Try to get extension from filename
            file_ext = str(file_path).split('.')[-1].lower()
        source_type = 'xlsx' if file_ext in ['xlsx', 'xls'] else file_ext
        
        # Extract data
        df = Extractor.extract(source_type, {"file_path": str(file_path)})
        initial_rows = len(df)
        initial_columns = len(df.columns)
        
        # Get input preview (first 10 rows)
        input_preview = {
            "columns": df.columns.tolist(),
            "rows": df.head(10).to_dict(orient='records'),
            "totalRows": initial_rows,
            "totalColumns": initial_columns
        }
        
        # Transform data - Always remove duplicates and clean data (same as CSV/JSON)
        transformed_df = df.copy()
        
        # Remove duplicates (same as frontend does for CSV/JSON)
        rows_before_dedup = len(transformed_df)
        transformed_df = transformed_df.drop_duplicates()
        duplicate_count = rows_before_dedup - len(transformed_df)
        
        # Clean data: trim whitespace from string columns
        for col in transformed_df.columns:
            if transformed_df[col].dtype == 'object':
                transformed_df[col] = transformed_df[col].astype(str).str.strip()
        
        # Remove rows where all values are empty
        transformed_df = transformed_df.dropna(how='all')
        transformed_df = transformed_df[transformed_df.astype(str).ne('').any(axis=1)]
        
        rows_after_transform = len(transformed_df)
        
        # Apply additional transformations if provided
        if request.transformations:
            transformed_df = Transformer.transform(transformed_df, request.transformations)
            rows_after_transform = len(transformed_df)
        
        # Generate output file
        output_file_id = str(uuid.uuid4())
        output_filename = f"{output_file_id}_processed.xlsx"
        output_path = PROCESSED_DIR / output_filename
        
        # Load to XLSX
        Loader.load(transformed_df, "xlsx", {"file_path": str(output_path)})
        
        # Get output preview (first 10 rows)
        output_preview = {
            "columns": transformed_df.columns.tolist(),
            "rows": transformed_df.head(10).to_dict(orient='records'),
            "totalRows": len(transformed_df),
            "totalColumns": len(transformed_df.columns)
        }
        
        # Prepare pipeline steps (same structure as CSV/JSON)
        pipeline_steps = [
            {
                "name": "EXTRACT",
                "status": "success",
                "size": f"{initial_rows} elements"
            },
            {
                "name": "LOAD",
                "status": "success",
                "rowsProcessed": rows_after_transform
            },
            {
                "name": "TRANSFORM_1",
                "status": "success",
                "size": f"{rows_after_transform} elements",
                "transformer": "FunctionTransformer"
            }
        ]
        
        # Convert output data to records for frontend
        output_data = transformed_df.to_dict(orient='records')
        
        return {
            "status": "success",
            "input_preview": input_preview,
            "output_preview": output_preview,
            "output_file": f"/api/files/download/{output_file_id}",
            "output_file_name": output_filename,
            "pipeline_steps": pipeline_steps,
            "output_data": output_data,
            "duplicate_count": duplicate_count,
            "rows_before": initial_rows,
            "rows_after": rows_after_transform
        }
    except Exception as e:
        logger.error(f"Error processing file: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/files/download/{file_id}")
async def download_file(file_id: str):
    """Download a processed file"""
    try:
        # Find the processed file
        processed_files = list(PROCESSED_DIR.glob(f"{file_id}_*"))
        if not processed_files:
            raise HTTPException(status_code=404, detail="File not found")
        
        file_path = processed_files[0]
        return FileResponse(
            path=str(file_path),
            filename=file_path.name,
            media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    except Exception as e:
        logger.error(f"Error downloading file: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Catch-all route for frontend client-side routing
# This MUST be at the end, after all API routes, so it doesn't intercept API calls
@app.get("/{full_path:path}")
async def serve_frontend(full_path: str):
    """Serve frontend for client-side routing (catch-all route)"""
    # Don't serve frontend for API routes (shouldn't reach here due to route order, but safety check)
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="API endpoint not found")
    
    # Check if it's a static file request (like favicon, etc.)
    file_path = FRONTEND_DIST / full_path
    if file_path.exists() and file_path.is_file():
        return FileResponse(str(file_path))
    
    # For all other routes, serve index.html (for client-side routing)
    index_path = FRONTEND_DIST / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    
    raise HTTPException(status_code=404, detail="Not found")


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=["."]
    )

