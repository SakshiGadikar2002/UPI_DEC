from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, UploadFile, File, Query, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.exception_handlers import http_exception_handler
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from typing import List, Optional, Dict, Any, Set
import uvicorn
from datetime import datetime, timedelta
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

from dotenv import load_dotenv
load_dotenv(override=True)
import hashlib
import secrets

from etl.extractor import Extractor
from etl.transformer import Transformer
from etl.loader import Loader
from etl.job_manager import JobManager
from database import (
    connect_to_postgres,
    close_postgres_connection,
    get_pool,
    create_user,
    get_user_by_email,
    update_user_last_login,
    log_user_event,
    save_uploaded_file_metadata,
    get_pipeline_state,
    update_pipeline_counts,
    get_failed_api_calls,
)
from models.websocket_data import WebSocketMessage, WebSocketBatch
from models.connector import (
    ConnectorCreate, ConnectorUpdate, ConnectorResponse, 
    ConnectorStatusResponse, AuthType, ConnectorStatus
)
from services.encryption import get_encryption_service
from services.connector_manager import get_connector_manager
from services.message_processor import MessageProcessor
from services.websocket_stream_manager import WebSocketStreamManager

from job_scheduler import start_job_scheduler, stop_job_scheduler
from job_scheduler.pipeline_tracker import start_pipeline_tracker

# --- Auto-insert scheduled API connectors if missing ---
import asyncio as _asyncio
SCHEDULED_APIS = [
    {
        "connector_id": "binance_orderbook",
        "name": "Binance - Order Book (BTC/USDT)",
        "api_url": "https://api.binance.com/api/v3/depth?symbol=BTCUSDT",
        "http_method": "GET",
        "auth_type": "None",
        "status": "active",
        "polling_interval": 10000,
        "protocol_type": "REST",
        "exchange_name": "Binance"
    },
    {
        "connector_id": "binance_prices",
        "name": "Binance - Current Prices",
        "api_url": "https://api.binance.com/api/v3/ticker/price",
        "http_method": "GET",
        "auth_type": "None",
        "status": "active",
        "polling_interval": 10000,
        "protocol_type": "REST",
        "exchange_name": "Binance"
    },
    {
        "connector_id": "binance_24hr",
        "name": "Binance - 24hr Ticker",
        "api_url": "https://api.binance.com/api/v3/ticker/24hr",
        "http_method": "GET",
        "auth_type": "None",
        "status": "active",
        "polling_interval": 10000,
        "protocol_type": "REST",
        "exchange_name": "Binance"
    },
    {
        "connector_id": "coingecko_global",
        "name": "CoinGecko - Global Market",
        "api_url": "https://api.coingecko.com/api/v3/global",
        "http_method": "GET",
        "auth_type": "None",
        "status": "active",
        "polling_interval": 10000,
        "protocol_type": "REST",
        "exchange_name": "CoinGecko"
    },
    {
        "connector_id": "coingecko_top",
        "name": "CoinGecko - Top Cryptocurrencies",
        "api_url": "https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=100&page=1&sparkline=false",
        "http_method": "GET",
        "auth_type": "None",
        "status": "active",
        "polling_interval": 10000,
        "protocol_type": "REST",
        "exchange_name": "CoinGecko"
    },
    {
        "connector_id": "coingecko_trending",
        "name": "CoinGecko - Trending Coins",
        "api_url": "https://api.coingecko.com/api/v3/search/trending",
        "http_method": "GET",
        "auth_type": "None",
        "status": "active",
        "polling_interval": 10000,
        "protocol_type": "REST",
        "exchange_name": "CoinGecko"
    },
    {
        "connector_id": "cryptocompare_multi",
        "name": "CryptoCompare - Multi Price",
        "api_url": "https://min-api.cryptocompare.com/data/pricemulti?fsyms=BTC,ETH,BNB&tsyms=USD",
        "http_method": "GET",
        "auth_type": "None",
        "status": "active",
        "polling_interval": 10000,
        "protocol_type": "REST",
        "exchange_name": "CryptoCompare"
    },
    {
        "connector_id": "cryptocompare_top",
        "name": "CryptoCompare - Top Coins",
        "api_url": "https://min-api.cryptocompare.com/data/top/mktcapfull?limit=10&tsym=USD",
        "http_method": "GET",
        "auth_type": "None",
        "status": "active",
        "polling_interval": 10000,
        "protocol_type": "REST",
        "exchange_name": "CryptoCompare"
    }
]

async def ensure_scheduled_connectors():
    pool = get_pool()
    async with pool.acquire() as conn:
        for api in SCHEDULED_APIS:
            exists = await conn.fetchval(
                "SELECT 1 FROM api_connectors WHERE connector_id = $1", api["connector_id"]
            )
            if not exists:
                await conn.execute(
                    """
                    INSERT INTO api_connectors (connector_id, name, api_url, http_method, auth_type, status, polling_interval, protocol_type, exchange_name)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    """,
                    api["connector_id"], api["name"], api["api_url"], api["http_method"], api["auth_type"], api["status"], api["polling_interval"], api["protocol_type"], api["exchange_name"]
                )
                logger.info(f"[INIT] Inserted scheduled connector: {api['connector_id']}")


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Authentication helpers
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
active_tokens: Dict[str, Dict[str, Any]] = {}


class UserCreate(BaseModel):
    email: str
    password: str
    full_name: Optional[str] = None


class UserInfo(BaseModel):
    id: int
    email: str
    full_name: Optional[str] = None
    created_at: datetime
    last_login_at: Optional[datetime] = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


def _hash_password(password: str) -> str:
    """Hash a password using SHA256"""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def _verify_password(password: str, stored_hash: str) -> bool:
    """Constant-time password comparison"""
    return secrets.compare_digest(_hash_password(password), stored_hash)


async def authenticate_user(email: str, password: str):
    """Validate user credentials and return user record"""
    user = await get_user_by_email(email)
    if not user or not user["is_active"]:
        return None
    if not _verify_password(password, user["password_hash"]):
        return None
    return user


async def get_current_user(request: Request, token: str = Depends(oauth2_scheme)):
    """Dependency to retrieve the current authenticated user"""
    payload = active_tokens.get(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user = await get_user_by_email(payload["email"])
    if not user or not user["is_active"]:
        raise HTTPException(status_code=401, detail="User disabled or not found")

    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    await log_user_event(
        user["id"],
        "access",
        ip_address=client_ip,
        user_agent=user_agent,
        metadata={"path": request.url.path, "method": request.method},
    )
    request.state.current_user = user
    return user

# Global scheduler references
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
            start_job_scheduler(loop, save_to_database, save_api_items_to_database)
            logger.info("[STARTUP] ✅ Job scheduler initialized and running")
            print("[STARTUP] ✅ Job scheduler initialized and running")
            print("[STARTUP] 📊 Scheduled APIs will run every 30 minutes")
        except Exception as e:
            logger.error(f"[STARTUP] ❌ Failed to start job scheduler: {e}")
            print(f"[STARTUP] ❌ Failed to start job scheduler: {e}")
            import traceback
            traceback.print_exc()
    
    # Run scheduler starts in the event loop after a brief delay to ensure app is ready
    asyncio.get_event_loop().call_soon(start_scheduler_later)
    
    # Start pipeline tracker
    try:
        loop = asyncio.get_event_loop()
        await start_pipeline_tracker(loop)
        logger.info("[STARTUP] ✅ Pipeline tracker initialized")
    except Exception as e:
        logger.error(f"[STARTUP] ❌ Failed to start pipeline tracker: {e}")

    yield
    
    # Shutdown: Stop schedulers and close PostgreSQL connection
    try:
        stop_job_scheduler()
        logger.info("[SHUTDOWN] Job scheduler stopped successfully")
    except Exception as e:
        logger.error(f"[SHUTDOWN] Error stopping job scheduler: {e}")
    
    await close_postgres_connection()


app = FastAPI(title="arithpipe API", version="1.0.0", lifespan=lifespan)

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

# Create uploads directory with subfolders for each file type
UPLOADS_DIR = BASE_DIR / "backend" / "uploads"
UPLOADS_DIR.mkdir(exist_ok=True)

# Create uploads subfolders for each file type
UPLOADS_CSV_DIR = UPLOADS_DIR / "csv"
UPLOADS_JSON_DIR = UPLOADS_DIR / "json"
UPLOADS_XLSX_DIR = UPLOADS_DIR / "xlsx"
UPLOADS_CSV_DIR.mkdir(exist_ok=True)
UPLOADS_JSON_DIR.mkdir(exist_ok=True)
UPLOADS_XLSX_DIR.mkdir(exist_ok=True)

# Create processed directory with subfolders for each file type
PROCESSED_DIR = BASE_DIR / "backend" / "processed"
PROCESSED_DIR.mkdir(exist_ok=True)

PROCESSED_CSV_DIR = PROCESSED_DIR / "csv"
PROCESSED_JSON_DIR = PROCESSED_DIR / "json"
PROCESSED_XLSX_DIR = PROCESSED_DIR / "xlsx"
PROCESSED_CSV_DIR.mkdir(exist_ok=True)
PROCESSED_JSON_DIR.mkdir(exist_ok=True)
PROCESSED_XLSX_DIR.mkdir(exist_ok=True)

# Helper function to get correct directory based on file type
def get_uploads_dir_by_type(file_ext: str) -> Path:
    """Get uploads directory based on file type"""
    ext_lower = file_ext.lower()
    if ext_lower == 'csv':
        return UPLOADS_CSV_DIR
    elif ext_lower == 'json':
        return UPLOADS_JSON_DIR
    elif ext_lower in ['xlsx', 'xls']:
        return UPLOADS_XLSX_DIR
    return UPLOADS_DIR

def get_processed_dir_by_type(file_ext: str) -> Path:
    """Get processed directory based on file type"""
    ext_lower = file_ext.lower()
    if ext_lower == 'csv':
        return PROCESSED_CSV_DIR
    elif ext_lower == 'json':
        return PROCESSED_JSON_DIR
    elif ext_lower in ['xlsx', 'xls']:
        return PROCESSED_XLSX_DIR
    return PROCESSED_DIR

if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST / "assets")), name="assets")
    logger.info(f"Static files mounted from: {FRONTEND_DIST}")
else:
    logger.warning(f"Frontend dist directory not found at: {FRONTEND_DIST}")

@app.exception_handler(StarletteHTTPException)
async def _spa_fallback_404(request: Request, exc: StarletteHTTPException):
    if exc.status_code != 404:
        return await http_exception_handler(request, exc)
    path = request.url.path
    method = request.method.upper()
    if path.startswith("/api") or path.startswith("/docs") or path.startswith("/redoc") or path.startswith("/openapi.json"):
        return await http_exception_handler(request, exc)
    if method not in ("GET", "HEAD"):
        return await http_exception_handler(request, exc)
    file_candidate = (FRONTEND_DIST / path.lstrip("/"))
    if file_candidate.exists() and file_candidate.is_file():
        return FileResponse(str(file_candidate))
    index_path = FRONTEND_DIST / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return await http_exception_handler(request, exc)

# Initialize job manager
job_manager = JobManager()

# Initialize encryption service
encryption_service = get_encryption_service()


# -------------------- Auth routes --------------------
@app.post("/auth/register", response_model=UserInfo)
async def register_user(user: UserCreate):
    """Register a new user who can receive alerts"""
    existing = await get_user_by_email(user.email)
    if existing:
        raise HTTPException(status_code=400, detail="User already exists")

    user_id = await create_user(user.email, _hash_password(user.password), user.full_name)
    if not user_id:
        raise HTTPException(status_code=400, detail="User could not be created")

    await log_user_event(user_id, "register")
    created = await get_user_by_email(user.email)
    return UserInfo(
        id=created["id"],
        email=created["email"],
        full_name=created["full_name"],
        created_at=created["created_at"],
        last_login_at=created["last_login_at"],
    )


@app.post("/auth/login", response_model=TokenResponse)
async def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends()):
    """Login a user and issue a bearer token"""
    user = await authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = str(uuid.uuid4())
    active_tokens[token] = {"email": user["email"], "issued_at": datetime.utcnow().isoformat()}
    await update_user_last_login(user["id"])

    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    await log_user_event(
        user["id"],
        "login",
        ip_address=client_ip,
        user_agent=user_agent,
    )

    return TokenResponse(access_token=token)


@app.post("/auth/logout")
async def logout(request: Request, current_user=Depends(get_current_user)):
    """Invalidate the current bearer token"""
    auth_header = request.headers.get("authorization", "")
    token = auth_header.replace("Bearer", "").strip()
    if token in active_tokens:
        active_tokens.pop(token, None)
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    await log_user_event(
        current_user["id"],
        "logout",
        ip_address=client_ip,
        user_agent=user_agent,
    )
    return {"status": "ok"}


@app.get("/auth/me", response_model=UserInfo)
async def me(current_user=Depends(get_current_user)):
    """Return current user profile"""
    return UserInfo(
        id=current_user["id"],
        email=current_user["email"],
        full_name=current_user["full_name"],
        created_at=current_user["created_at"],
        last_login_at=current_user["last_login_at"],
    )



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
async def save_api_items_to_database(connector_id: str, api_name: str, response_data: Any, response_time_ms: int):
    """Save individual items from API response to api_connector_items table"""
    try:
        logger.info(f"[ITEMS] 🔄 Processing items for {connector_id} ({api_name})...")
        pool = get_pool()
        items_inserted = 0
        
        async with pool.acquire() as conn:
            # Helper function to extract items from different API formats
            items = _extract_api_items(connector_id, response_data)
            logger.info(f"[ITEMS] Extracted {len(items)} items from {connector_id}")
            
            timestamp = datetime.utcnow()
            source_id = hashlib.md5(f"{connector_id}_{timestamp}".encode()).hexdigest()[:16]
            session_id = str(uuid.uuid4())
            
            for idx, item in enumerate(items):
                try:
                    coin_name = item.get("coin_name", "-")
                    coin_symbol = item.get("coin_symbol", "-")
                    price = item.get("price")
                    market_cap = item.get("market_cap")
                    volume_24h = item.get("volume_24h")
                    price_change_24h = item.get("price_change_24h")
                    market_cap_rank = item.get("market_cap_rank")
                    
                    # Ensure price is not None
                    if price is None:
                        price = 0.0
                    
                    # Determine exchange based on connector_id or use provided exchange
                    exchange_value = "scheduled_api"
                    if connector_id.startswith("binance"):
                        exchange_value = "Binance"
                    elif connector_id.startswith("coingecko"):
                        exchange_value = "CoinGecko"
                    elif connector_id.startswith("cryptocompare"):
                        exchange_value = "CryptoCompare"
                    
                    await conn.execute("""
                        INSERT INTO api_connector_items (
                            connector_id, api_name, timestamp, exchange, coin_name, coin_symbol,
                            price, market_cap, volume_24h, price_change_24h, market_cap_rank,
                            item_data, raw_item, item_index, response_time_ms, source_id, session_id
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17)
                    """,
                        connector_id, api_name, timestamp, exchange_value,
                        coin_name, coin_symbol, price, market_cap, volume_24h, price_change_24h, market_cap_rank,
                        json.dumps(item), json.dumps(item.get("raw_item", {})), idx, response_time_ms, source_id, session_id
                    )
                    items_inserted += 1
                except Exception as item_error:
                    logger.warning(f"[ITEMS] Failed to insert item {idx} for {connector_id}: {item_error}")
                    continue
            
            if items_inserted > 0:
                logger.info(f"[ITEMS] ✅ Inserted {items_inserted} items from {api_name} ({connector_id})")
            else:
                logger.warning(f"[ITEMS] ⚠️ No items inserted for {connector_id}")
            
            # Update visualization_data table for coingecko APIs
            # This ensures visualization_data is updated when scheduler saves data
            if connector_id in ["coingecko_top", "coingecko_global"]:
                try:
                    # Schedule visualization update in background
                    loop = asyncio.get_event_loop()
                    loop.create_task(update_visualization_data(connector_id, response_data, timestamp, response_data))
                    logger.debug(f"[ITEMS] Scheduled visualization_data update for {connector_id}")
                except Exception as viz_error:
                    logger.warning(f"[ITEMS] Could not schedule visualization_data update for {connector_id}: {viz_error}")
            
            # Update pipeline counts immediately after saving items (real-time count updates)
            # Schedule in background to avoid blocking, but ensure it runs
            if items_inserted > 0:
                try:
                    # Use create_task to run async without blocking
                    loop = asyncio.get_event_loop()
                    loop.create_task(update_pipeline_counts(connector_id))
                except Exception as count_error:
                    logger.error(f"[ITEMS] ❌ Could not schedule pipeline count update for {connector_id}: {count_error}", exc_info=True)
    
    except Exception as e:
        logger.error(f"[ITEMS] ❌ Error saving API items: {e}")
        import traceback
        traceback.print_exc()


def _extract_api_items(connector_id: str, response_data: dict) -> List[dict]:
    """
    Extract individual items from various API response formats.
    Returns a list of normalized item dictionaries.
    """
    items = []
    
    try:
        # CoinGecko markets format: list of coins with price, market_cap, etc.
        if connector_id == "coingecko_top" and isinstance(response_data, list):
            for item in response_data:
                items.append({
                    "coin_name": item.get("name", "-"),
                    "coin_symbol": item.get("symbol", "-").upper(),
                    "price": item.get("current_price"),
                    "market_cap": item.get("market_cap"),
                    "volume_24h": item.get("total_volume"),
                    "price_change_24h": item.get("price_change_percentage_24h"),
                    "market_cap_rank": item.get("market_cap_rank"),
                    "raw_item": item
                })
        
        # CoinGecko trending format
        elif connector_id == "coingecko_trending" and isinstance(response_data, dict):
            coins = response_data.get("coins", [])
            for item in coins:
                coin_data = item.get("item", {})
                items.append({
                    "coin_name": coin_data.get("name", "-"),
                    "coin_symbol": coin_data.get("symbol", "-").upper(),
                    "price": coin_data.get("data", {}).get("price"),
                    "market_cap_rank": coin_data.get("market_cap_rank"),
                    "raw_item": coin_data
                })
        
        # Binance ticker 24hr format: list of symbols with prices
        elif connector_id == "binance_24hr" and isinstance(response_data, list):
            for item in response_data:
                symbol = item.get("symbol", "-")
                items.append({
                    "coin_name": symbol,
                    "coin_symbol": symbol,
                    "price": float(item.get("lastPrice", 0)),
                    "volume_24h": float(item.get("quoteAssetVolume", 0)) if item.get("quoteAssetVolume") else None,
                    "price_change_24h": float(item.get("priceChangePercent", 0)) if item.get("priceChangePercent") else None,
                    "raw_item": item
                })
        
        # Binance current prices: list of symbol/price pairs
        elif connector_id == "binance_prices" and isinstance(response_data, list):
            for item in response_data:
                items.append({
                    "coin_name": item.get("symbol", "-"),
                    "coin_symbol": item.get("symbol", "-"),
                    "price": float(item.get("price", 0)) if item.get("price") else 0.0,
                    "raw_item": item
                })
        
        # CoinGecko global: extract from data field
        elif connector_id == "coingecko_global" and isinstance(response_data, dict):
            data = response_data.get("data", {})
            if data:
                items.append({
                    "coin_name": "Global Market Data",
                    "coin_symbol": "GLOBAL",
                    "price": data.get("btc_market_cap"),
                    "market_cap": data.get("total_market_cap", {}).get("usd"),
                    "volume_24h": data.get("total_volume", {}).get("usd"),
                    "raw_item": data
                })
        
        # CryptoCompare multi format: dict with symbols as keys
        elif connector_id == "cryptocompare_multi" and isinstance(response_data, dict):
            for symbol, prices in response_data.items():
                if isinstance(prices, dict) and "USD" in prices:
                    items.append({
                        "coin_name": symbol,
                        "coin_symbol": symbol,
                        "price": prices.get("USD"),
                        "raw_item": {"symbol": symbol, "data": prices}
                    })
        
        # CryptoCompare top format: nested data structure
        elif connector_id == "cryptocompare_top" and isinstance(response_data, dict):
            data = response_data.get("Data", [])
            if isinstance(data, list):
                for item in data:
                    coin_info = item.get("CoinInfo", {})
                    price_info = item.get("DISPLAY", {}).get("USD", {})
                    items.append({
                        "coin_name": coin_info.get("FullName", "-"),
                        "coin_symbol": coin_info.get("Symbol", "-"),
                        "price": float(price_info.get("PRICE", 0).replace("$", "").replace(",", "")) if price_info.get("PRICE") else None,
                        "market_cap": price_info.get("MKTCAP"),
                        "volume_24h": price_info.get("VOLUME24H"),
                        "price_change_24h": price_info.get("CHANGE24HOUR"),
                        "raw_item": item
                    })
        
        # Binance order book: extract bids/asks
        elif connector_id == "binance_orderbook" and isinstance(response_data, dict):
            bids = response_data.get("bids", [])
            asks = response_data.get("asks", [])
            
            if bids:
                best_bid = bids[0]
                items.append({
                    "coin_name": "BTC/USDT - Best Bid",
                    "coin_symbol": "BTC",
                    "price": float(best_bid[0]) if len(best_bid) > 0 else None,
                    "volume_24h": float(best_bid[1]) if len(best_bid) > 1 else None,
                    "raw_item": {"type": "best_bid", "data": best_bid}
                })
            
            if asks:
                best_ask = asks[0]
                items.append({
                    "coin_name": "BTC/USDT - Best Ask",
                    "coin_symbol": "BTC",
                    "price": float(best_ask[0]) if len(best_ask) > 0 else None,
                    "volume_24h": float(best_ask[1]) if len(best_ask) > 1 else None,
                    "raw_item": {"type": "best_ask", "data": best_ask}
                })
        
        # Default: if we have a list, treat each item as a separate entry
        elif isinstance(response_data, list) and len(response_data) > 0:
            for item in response_data:
                if isinstance(item, dict):
                    items.append({
                        "coin_name": item.get("name", item.get("symbol", "-")),
                        "coin_symbol": item.get("symbol", "-").upper(),
                        "price": item.get("price"),
                        "raw_item": item
                    })
        
        # If response is a dict and we didn't match above, store it as one item
        if len(items) == 0 and isinstance(response_data, dict):
            items.append({
                "coin_name": connector_id,
                "coin_symbol": connector_id.upper(),
                "price": response_data.get("price"),
                "raw_item": response_data
            })
    
    except Exception as e:
        logger.warning(f"[DB] Error extracting items for {connector_id}: {e}")
    
    return items if items else [{"coin_name": connector_id, "coin_symbol": connector_id, "price": 0.0, "raw_item": response_data}]


async def update_visualization_data(connector_id: str, data: Any, timestamp: datetime, raw_response: Any = None):
    """
    Update visualization_data table when new data arrives.
    This ensures visualization_data is always up-to-date for real-time monitoring.
    Uses the data parameter directly instead of querying the database again.
    """
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            # Handle coingecko_top (markets data)
            if connector_id == "coingecko_top":
                # Parse data if it's a string
                if isinstance(data, str):
                    try:
                        data = json.loads(data)
                    except:
                        pass
                
                if isinstance(raw_response, str):
                    try:
                        raw_response = json.loads(raw_response)
                    except:
                        pass
                
                # Reconstruct coins list from the data we just saved
                coins_list = []
                
                # Priority 1: data is a list (entire list stored in one row)
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict) and (item.get("id") or item.get("symbol") or item.get("name") or item.get("current_price") is not None):
                            coins_list.append(item)
                
                # Priority 2: data is a dict
                elif isinstance(data, dict):
                    # Check if this is a single coin object
                    if data.get("id") or data.get("symbol") or data.get("name") or data.get("current_price") is not None:
                        coins_list.append(data)
                    # Check if data contains a nested list/array
                    elif "data" in data and isinstance(data["data"], list):
                        coins_list.extend([item for item in data["data"] if isinstance(item, dict)])
                    # Check for other nested structures
                    elif any(isinstance(v, list) for v in data.values()):
                        for key, value in data.items():
                            if isinstance(value, list):
                                coins_list.extend([item for item in value if isinstance(item, dict) and (item.get("id") or item.get("symbol") or item.get("name"))])
                                break
                
                # Priority 3: raw_response contains the data
                if not coins_list and raw_response:
                    if isinstance(raw_response, list):
                        coins_list.extend([item for item in raw_response if isinstance(item, dict)])
                    elif isinstance(raw_response, dict) and raw_response.get("id"):
                        coins_list.append(raw_response)
                
                # If still no coins, try querying database as fallback
                if not coins_list:
                    logger.warning(f"[VIZ] No coins found in data, querying database as fallback for {connector_id}")
                    from datetime import timedelta
                    time_lower = timestamp - timedelta(seconds=2)
                    time_upper = timestamp + timedelta(seconds=2)
                    
                    rows = await conn.fetch("""
                        SELECT data, raw_response
                        FROM api_connector_data
                        WHERE connector_id = $1
                        AND timestamp >= $2
                        AND timestamp <= $3
                        ORDER BY id
                    """, connector_id, time_lower, time_upper)
                    
                    for row in rows:
                        row_data = row["data"]
                        row_raw = row.get("raw_response")
                        
                        if isinstance(row_data, str):
                            try:
                                row_data = json.loads(row_data)
                            except:
                                pass
                        
                        if isinstance(row_raw, str):
                            try:
                                row_raw = json.loads(row_raw)
                            except:
                                pass
                        
                        if isinstance(row_data, list):
                            for item in row_data:
                                if isinstance(item, dict) and (item.get("id") or item.get("symbol") or item.get("name")):
                                    coins_list.append(item)
                        elif isinstance(row_data, dict):
                            if row_data.get("id") or row_data.get("symbol") or row_data.get("name") or row_data.get("current_price") is not None:
                                coins_list.append(row_data)
                            elif "data" in row_data and isinstance(row_data["data"], list):
                                coins_list.extend([item for item in row_data["data"] if isinstance(item, dict)])
                        elif row_raw:
                            if isinstance(row_raw, list):
                                coins_list.extend([item for item in row_raw if isinstance(item, dict)])
                            elif isinstance(row_raw, dict) and row_raw.get("id"):
                                coins_list.append(row_raw)
                
                if coins_list:
                    # Save to visualization_data
                    await conn.execute("""
                        INSERT INTO visualization_data (data_type, timestamp, data, metadata, updated_at)
                        VALUES ($1, $2, $3, $4, NOW())
                        ON CONFLICT (data_type, timestamp) 
                        DO UPDATE SET 
                            data = EXCLUDED.data,
                            metadata = EXCLUDED.metadata,
                            updated_at = NOW()
                    """, 
                        "markets",
                        timestamp,
                        json.dumps(coins_list),
                        json.dumps({"source": connector_id, "total_coins": len(coins_list)})
                    )
                    logger.info(f"✅ [VIZ] Updated visualization_data: markets ({len(coins_list)} coins) at {timestamp}")
                    
                    # Broadcast update via WebSocket for real-time frontend updates
                    try:
                        await connection_manager.broadcast({
                            "type": "visualization_update",
                            "data_type": "markets",
                            "connector_id": connector_id,
                            "timestamp": timestamp.isoformat(),
                            "total_coins": len(coins_list),
                            "message": "Market data updated"
                        })
                        logger.debug(f"✅ [VIZ] Broadcasted WebSocket update for markets")
                    except Exception as ws_err:
                        logger.warning(f"[VIZ] Could not broadcast visualization update: {ws_err}")
                else:
                    logger.warning(f"[VIZ] No coins found to save for {connector_id}")
            
            # Handle coingecko_global (global stats)
            elif connector_id == "coingecko_global":
                # Parse data if it's a string
                if isinstance(data, str):
                    try:
                        data = json.loads(data)
                    except:
                        pass
                
                if isinstance(raw_response, str):
                    try:
                        raw_response = json.loads(raw_response)
                    except:
                        pass
                
                result = None
                
                # Try data field first
                if isinstance(data, dict):
                    result = data
                # Try raw_response as fallback
                elif raw_response and isinstance(raw_response, dict):
                    result = raw_response
                
                # If still no result, query database as fallback
                if not result:
                    logger.warning(f"[VIZ] No data found, querying database as fallback for {connector_id}")
                    row = await conn.fetchrow("""
                        SELECT data, raw_response
                        FROM api_connector_data
                        WHERE connector_id = $1
                        AND timestamp = $2
                        LIMIT 1
                    """, connector_id, timestamp)
                    
                    if row:
                        viz_data = row["data"]
                        row_raw = row.get("raw_response")
                        
                        if isinstance(viz_data, str):
                            try:
                                viz_data = json.loads(viz_data)
                            except:
                                pass
                        
                        if isinstance(row_raw, str):
                            try:
                                row_raw = json.loads(row_raw)
                            except:
                                pass
                        
                        result = viz_data if isinstance(viz_data, dict) else (row_raw if isinstance(row_raw, dict) else None)
                
                if result:
                    # Normalize field names
                    if "data" in result and isinstance(result["data"], dict):
                        if "total_volume" in result["data"] and "total_volume_24h" not in result["data"]:
                            result["data"]["total_volume_24h"] = result["data"]["total_volume"]
                    elif "total_volume" in result and "total_volume_24h" not in result:
                        result["total_volume_24h"] = result["total_volume"]
                    
                    # Save to visualization_data
                    await conn.execute("""
                        INSERT INTO visualization_data (data_type, timestamp, data, metadata, updated_at)
                        VALUES ($1, $2, $3, $4, NOW())
                        ON CONFLICT (data_type, timestamp) 
                        DO UPDATE SET 
                            data = EXCLUDED.data,
                            metadata = EXCLUDED.metadata,
                            updated_at = NOW()
                    """, 
                        "global_stats",
                        timestamp,
                        json.dumps(result),
                        json.dumps({"source": connector_id})
                    )
                    logger.info(f"✅ [VIZ] Updated visualization_data: global_stats at {timestamp}")
                    
                    # Broadcast update via WebSocket for real-time frontend updates
                    try:
                        await connection_manager.broadcast({
                            "type": "visualization_update",
                            "data_type": "global_stats",
                            "connector_id": connector_id,
                            "timestamp": timestamp.isoformat(),
                            "message": "Global stats updated"
                        })
                        logger.debug(f"✅ [VIZ] Broadcasted WebSocket update for global_stats")
                    except Exception as ws_err:
                        logger.warning(f"[VIZ] Could not broadcast visualization update: {ws_err}")
                else:
                    logger.warning(f"[VIZ] No global stats data found to save for {connector_id}")
    except Exception as e:
        logger.error(f"[VIZ] Failed to update visualization_data for {connector_id}: {e}", exc_info=True)


async def save_to_database(message: dict):
    """Save processed message to database"""
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            # Extract fields
            connector_id = message.get("connector_id") or "unknown"
            exchange = message.get("exchange") or "custom"
            instrument = message.get("instrument") or "-"
            price = message.get("price")
            if price is None:
                price = 0.0
            data = message.get("data")
            if data is None:
                data = {}
            message_type = message.get("message_type") or "api_response"
            timestamp_str = message.get("timestamp")
            raw_response = message.get("raw_response")
            if raw_response is None:
                raw_response = {}
            status_code = message.get("status_code")
            if status_code is None:
                status_code = 200
            response_time_ms = message.get("response_time_ms")
            if response_time_ms is None:
                response_time_ms = 0
            # Log warning if any required field is missing
            required_fields = {
                "connector_id": connector_id,
                "exchange": exchange,
                "instrument": instrument,
                "price": price,
                "data": data,
                "message_type": message_type,
                "timestamp": timestamp_str,
            }
            for k, v in required_fields.items():
                if v in [None, "", {}, []]:
                    logger.warning(f"[DB] Field '{k}' is missing or empty, using default value: {v}")
            
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
            
            # Helper to persist a single row so list payloads fan out into multiple records
            async def _insert_row(row_data, row_raw, row_price, row_instrument, row_source_id_suffix=None):
                nonlocal connector_id
                row_source_id = source_id if row_source_id_suffix is None else f"{source_id}-{row_source_id_suffix}"
                try:
                    return await conn.fetchval(
                        """
                        INSERT INTO api_connector_data (
                            connector_id, timestamp, exchange, instrument, price, data, 
                            message_type, raw_response, status_code, response_time_ms, source_id, session_id
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                        RETURNING id
                        """,
                        connector_id,
                        timestamp,
                        exchange,
                        row_instrument,
                        row_price,
                        json.dumps(row_data),
                        message_type,
                        json.dumps(row_raw) if row_raw is not None else None,
                        status_code,
                        response_time_ms,
                        row_source_id,
                        session_id,
                    )
                except Exception as fk_error:
                    error_msg = str(fk_error)
                    if "foreign key constraint" in error_msg.lower():
                        # Allow scheduled APIs without a connector record
                        try:
                            connector_id = f"scheduled_{connector_id}"
                            return await conn.fetchval(
                                """
                                INSERT INTO api_connector_data (
                                    connector_id, timestamp, exchange, instrument, price, data, 
                                    message_type, raw_response, status_code, response_time_ms, source_id, session_id
                                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                                RETURNING id
                                """,
                                connector_id,
                                timestamp,
                                exchange,
                                row_instrument,
                                row_price,
                                json.dumps(row_data),
                                message_type,
                                json.dumps(row_raw) if row_raw is not None else None,
                                status_code,
                                response_time_ms,
                                row_source_id,
                                session_id,
                            )
                        except Exception as retry_error:
                            # Re-raise with more context
                            raise Exception(f"Foreign key constraint error (retry failed): {str(retry_error)}")
                    else:
                        # Re-raise with more context about the database error
                        raise Exception(f"Database insert error: {error_msg}")

            inserted_ids = []
            records_saved = 0

            if isinstance(data, list):
                for idx, item in enumerate(data):
                    row_data = item if isinstance(item, (dict, list)) else {"value": item}
                    row_raw = raw_response if raw_response is not None else row_data
                    row_price = (
                        row_data.get("price")
                        if isinstance(row_data, dict)
                        else price
                    ) or price
                    row_instrument = (
                        row_data.get("symbol")
                        if isinstance(row_data, dict)
                        else instrument
                    ) or instrument
                    row_id = await _insert_row(row_data, row_raw, row_price, row_instrument, idx)
                    inserted_ids.append(row_id)
                    records_saved += 1
            else:
                row_data = data
                row_raw = raw_response
                row_id = await _insert_row(row_data, row_raw, price, instrument)
                inserted_ids.append(row_id)
                records_saved = 1

            # Note: websocket_messages table is ONLY for websocket APIs (OKX, Binance, custom websocket)
            # REST APIs should NOT write to websocket_messages - removed backward compatibility insert

            logger.info(
                f"[DB] ✅ Saved {records_saved} record(s) to database for connector_id={connector_id}, exchange={exchange}, timestamp={timestamp}"
            )
            print(
                f"[DB] ✅ Saved {records_saved} record(s) to database for connector_id={connector_id}, exchange={exchange}"
            )
            
            # For manually run integrated APIs, also save to api_connector_items
            # Scheduled APIs already save via scheduler callback, so skip them here
            is_scheduled_api = connector_id in [api.get("connector_id", api.get("id")) for api in SCHEDULED_APIS]
            is_manual_integrated = not is_scheduled_api and message_type in ["api_response", "scheduled_api_call"]
            
            if is_manual_integrated and isinstance(data, (list, dict)):
                # Get API name from api_connectors table
                api_name = connector_id
                try:
                    api_row = await conn.fetchrow(
                        "SELECT name FROM api_connectors WHERE connector_id = $1",
                        connector_id
                    )
                    if api_row:
                        api_name = api_row.get("name", connector_id)
                except:
                    pass
                
                # Schedule items save in background (don't block main save)
                try:
                    # Use asyncio.create_task to run in background
                    loop = asyncio.get_event_loop()
                    loop.create_task(save_api_items_to_database(connector_id, api_name, data, response_time_ms))
                except Exception as items_error:
                    logger.warning(f"[DB] Could not schedule items save for manual API {connector_id}: {items_error}")

            # Update visualization_data table in background for real-time updates
            # This ensures visualization_data is always up-to-date when new data arrives
            if connector_id in ["coingecko_top", "coingecko_global"]:
                try:
                    # Schedule visualization update in background (don't block main save)
                    # Pass raw_response so we can use it if data is not in expected format
                    loop = asyncio.get_event_loop()
                    loop.create_task(update_visualization_data(connector_id, data, timestamp, raw_response))
                    logger.debug(f"[DB] Scheduled visualization_data update for {connector_id}")
                except Exception as viz_error:
                    logger.error(f"[DB] Could not schedule visualization_data update for {connector_id}: {viz_error}", exc_info=True)

            # Update pipeline counts immediately after saving (real-time count updates)
            # Schedule in background to avoid blocking, but ensure it runs
            try:
                # Use create_task to run async without blocking
                loop = asyncio.get_event_loop()
                loop.create_task(update_pipeline_counts(connector_id))
            except Exception as count_error:
                logger.error(f"[DB] ❌ Could not schedule pipeline count update for {connector_id}: {count_error}", exc_info=True)

            # Return metadata (include all IDs so callers can log details/counts)
            return {
                "ids": inserted_ids,
                "records_saved": records_saved,
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
                "response_time_ms": response_time_ms,
            }
    except Exception as e:
        error_type = type(e).__name__
        error_message = str(e)
        logger.error(f"Error saving to database: {e}", exc_info=True)
        import traceback
        traceback.print_exc()
        # Return error details instead of None
        return {
            "error": True,
            "error_type": error_type,
            "error_message": error_message,
            "error_details": str(e)
        }

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

message_processor = MessageProcessor(
    db_callback=save_to_database,
    websocket_callback=broadcast_to_websocket
)

# Initialize connector manager with message processor
connector_manager = get_connector_manager(message_processor)


# ==================== Job Scheduler Setup ====================

async def continuous_visualization_updater():
    """
    Background task that continuously updates visualization_data every 5 seconds.
    This ensures frontend always has fresh data even if scheduler is slow.
    """
    await asyncio.sleep(5)  # Wait 5 seconds after startup before starting
    
    while True:
        try:
            pool = get_pool()
            async with pool.acquire() as conn:
                # Update markets data (coingecko_top)
                latest_row = await conn.fetchrow("""
                    SELECT timestamp
                    FROM api_connector_data
                    WHERE connector_id = 'coingecko_top'
                    ORDER BY timestamp DESC
                    LIMIT 1
                """)
                
                if latest_row:
                    latest_timestamp = latest_row["timestamp"]
                    from datetime import timedelta
                    time_lower = latest_timestamp - timedelta(seconds=2)
                    time_upper = latest_timestamp + timedelta(seconds=2)
                    
                    rows = await conn.fetch("""
                        SELECT data, raw_response, timestamp
                        FROM api_connector_data
                        WHERE connector_id = 'coingecko_top'
                        AND timestamp >= $1
                        AND timestamp <= $2
                        ORDER BY id
                    """, time_lower, time_upper)
                    
                    if rows:
                        coins_list = []
                        for row in rows:
                            row_data = row["data"]
                            row_raw = row.get("raw_response")
                            
                            if isinstance(row_data, str):
                                try:
                                    row_data = json.loads(row_data)
                                except:
                                    pass
                            
                            if isinstance(row_raw, str):
                                try:
                                    row_raw = json.loads(row_raw)
                                except:
                                    pass
                            
                            if isinstance(row_data, list):
                                for item in row_data:
                                    if isinstance(item, dict) and (item.get("id") or item.get("symbol") or item.get("name") or item.get("current_price") is not None):
                                        coins_list.append(item)
                            elif isinstance(row_data, dict):
                                if row_data.get("id") or row_data.get("symbol") or row_data.get("name") or row_data.get("current_price") is not None:
                                    coins_list.append(row_data)
                                elif "data" in row_data and isinstance(row_data["data"], list):
                                    coins_list.extend([item for item in row_data["data"] if isinstance(item, dict)])
                            elif row_raw:
                                if isinstance(row_raw, list):
                                    coins_list.extend([item for item in row_raw if isinstance(item, dict)])
                                elif isinstance(row_raw, dict) and row_raw.get("id"):
                                    coins_list.append(row_raw)
                        
                        if coins_list:
                            # Update visualization_data
                            await conn.execute("""
                                INSERT INTO visualization_data (data_type, timestamp, data, metadata, updated_at)
                                VALUES ($1, $2, $3, $4, NOW())
                                ON CONFLICT (data_type, timestamp) 
                                DO UPDATE SET 
                                    data = EXCLUDED.data,
                                    metadata = EXCLUDED.metadata,
                                    updated_at = NOW()
                            """, 
                                "markets",
                                latest_timestamp,
                                json.dumps(coins_list),
                                json.dumps({"source": "coingecko_top", "total_coins": len(coins_list), "auto_update": True})
                            )
                            
                            # Broadcast WebSocket update
                            try:
                                await connection_manager.broadcast({
                                    "type": "visualization_update",
                                    "data_type": "markets",
                                    "connector_id": "coingecko_top",
                                    "timestamp": latest_timestamp.isoformat(),
                                    "total_coins": len(coins_list),
                                    "message": "Market data updated (auto-refresh)"
                                })
                            except:
                                pass
                
                # Update global stats (coingecko_global)
                global_row = await conn.fetchrow("""
                    SELECT data, raw_response, timestamp
                    FROM api_connector_data
                    WHERE connector_id = 'coingecko_global'
                    ORDER BY timestamp DESC
                    LIMIT 1
                """)
                
                if global_row:
                    viz_data = global_row["data"]
                    raw_response = global_row.get("raw_response")
                    timestamp = global_row["timestamp"]
                    
                    if isinstance(viz_data, str):
                        try:
                            viz_data = json.loads(viz_data)
                        except:
                            pass
                    
                    if isinstance(raw_response, str):
                        try:
                            raw_response = json.loads(raw_response)
                        except:
                            pass
                    
                    result = viz_data if isinstance(viz_data, dict) else (raw_response if isinstance(raw_response, dict) else None)
                    
                    if result:
                        # Normalize field names
                        if "data" in result and isinstance(result["data"], dict):
                            if "total_volume" in result["data"] and "total_volume_24h" not in result["data"]:
                                result["data"]["total_volume_24h"] = result["data"]["total_volume"]
                        elif "total_volume" in result and "total_volume_24h" not in result:
                            result["total_volume_24h"] = result["total_volume"]
                        
                        # Update visualization_data
                        await conn.execute("""
                            INSERT INTO visualization_data (data_type, timestamp, data, metadata, updated_at)
                            VALUES ($1, $2, $3, $4, NOW())
                            ON CONFLICT (data_type, timestamp) 
                            DO UPDATE SET 
                                data = EXCLUDED.data,
                                metadata = EXCLUDED.metadata,
                                updated_at = NOW()
                        """, 
                            "global_stats",
                            timestamp,
                            json.dumps(result),
                            json.dumps({"source": "coingecko_global", "auto_update": True})
                        )
                        
                        # Broadcast WebSocket update
                        try:
                            await connection_manager.broadcast({
                                "type": "visualization_update",
                                "data_type": "global_stats",
                                "connector_id": "coingecko_global",
                                "timestamp": timestamp.isoformat(),
                                "message": "Global stats updated (auto-refresh)"
                            })
                        except:
                            pass
        except Exception as e:
            logger.warning(f"[AUTO-UPDATE] Error in continuous visualization updater: {e}")
        
        # Wait 5 seconds before next update
        await asyncio.sleep(5)


@app.on_event("startup")
async def startup_job_scheduler():
    """Start job scheduler on application startup."""
    global _job_scheduler
    try:
        loop = asyncio.get_event_loop()
        # Ensure scheduled connectors exist before starting scheduler
        await ensure_scheduled_connectors()
        _job_scheduler = start_job_scheduler(loop, save_to_database, save_api_items_to_database)
        logger.info("[STARTUP] Job scheduler initialized and running")
        logger.info("[STARTUP] WebSocket Stream Manager initialized (persistence-first flow)")
        
        # Start continuous visualization updater (runs every 5 seconds)
        asyncio.create_task(continuous_visualization_updater())
        logger.info("[STARTUP] ✅ Continuous visualization updater started (updates every 5 seconds)")
    except Exception as e:
        logger.error(f"[STARTUP] Failed to start job scheduler: {e}")
        import traceback
        traceback.print_exc()


@app.on_event("shutdown")
async def shutdown_job_scheduler():
    """Stop job scheduler and WebSocket streams on application shutdown."""
    try:
        stop_job_scheduler()
        logger.info("[SHUTDOWN] Job scheduler stopped successfully")
    except Exception as e:
        logger.error(f"[SHUTDOWN] Error stopping job scheduler: {e}")
    
    try:
        await websocket_stream_manager.shutdown()
        logger.info("[SHUTDOWN] WebSocket Stream Manager shut down successfully")
    except Exception as e:
        logger.error(f"[SHUTDOWN] Error shutting down WebSocket Stream Manager: {e}")
# ================================================================


class ETLJobRequest(BaseModel):
    name: str
    source_type: str  # "csv", "json", "database" (api removed - pipeline only reads from database)
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
    return {"message": "arithpipe API", "version": "1.0.0"}


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


# CoinGecko Data Endpoints - Read from database (enforces API → Database → Backend → Frontend architecture)
# All external API data must first be persisted by backend services (scheduler/connectors) before consumption


@app.get("/api/crypto/global-stats")
async def get_global_crypto_stats():
    """
    Fetch global cryptocurrency market statistics from database.
    Data must first be persisted by backend scheduler (connector_id: coingecko_global).
    Enforces architecture: API → Database → Backend → Frontend
    
    Reads normalized rows from database and reconstructs the expected aggregated object format.
    """
    try:
        pool = get_pool()
        connector_id = "coingecko_global"
        
        async with pool.acquire() as conn:
            # Try visualization_data table first (optimized for visualization)
            viz_row = await conn.fetchrow("""
                SELECT data, timestamp, metadata
                FROM visualization_data
                WHERE data_type = 'global_stats'
                ORDER BY timestamp DESC
                LIMIT 1
            """)
            
            if viz_row:
                # Use visualization_data (already processed and ready)
                data = viz_row["data"]
                if isinstance(data, str):
                    try:
                        data = json.loads(data)
                    except:
                        pass
                
                logger.info(f"Returning global stats from visualization_data (timestamp: {viz_row['timestamp']})")
                response = JSONResponse(content=data)
                response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
                response.headers["Pragma"] = "no-cache"
                response.headers["Expires"] = "0"
                return response
            
            # Fallback to api_connector_data if visualization_data not available
            # Get the most recent global stats data from database
            # Global stats is stored as a single row with the full response
            row = await conn.fetchrow("""
                SELECT data, timestamp, raw_response
                FROM api_connector_data
                WHERE connector_id = $1
                ORDER BY timestamp DESC
                LIMIT 1
            """, connector_id)
            
            if not row:
                raise HTTPException(
                    status_code=404,
                    detail=f"No data found for {connector_id}. Ensure the scheduler is running and has fetched data."
                )
            
            # Extract data from JSONB column - could be stored as dict or string
            data = row["data"]
            raw_response = row.get("raw_response")
            
            # Handle string JSON (if stored as string)
            if isinstance(data, str):
                try:
                    import json
                    data = json.loads(data)
                except:
                    pass
            
            if isinstance(raw_response, str):
                try:
                    import json
                    raw_response = json.loads(raw_response)
                except:
                    pass
            
            # Reconstruct the expected format
            result = None
            
            # Try data field first
            if isinstance(data, dict):
                result = data
            # Try raw_response as fallback
            elif raw_response and isinstance(raw_response, dict):
                result = raw_response
            else:
                raise HTTPException(
                    status_code=500,
                    detail=f"Unexpected data format in database - expected dict. "
                           f"Found data type: {type(data).__name__}, raw_response type: {type(raw_response).__name__}"
                )
                
                # Normalize field names - CoinGecko uses 'total_volume' but frontend expects 'total_volume_24h'
                if "data" in result and isinstance(result["data"], dict):
                    if "total_volume" in result["data"] and "total_volume_24h" not in result["data"]:
                        result["data"]["total_volume_24h"] = result["data"]["total_volume"]
                elif "total_volume" in result and "total_volume_24h" not in result:
                    result["total_volume_24h"] = result["total_volume"]
                
            # Save to visualization_data table for easy monitoring
            try:
                await conn.execute("""
                    INSERT INTO visualization_data (data_type, timestamp, data, metadata, updated_at)
                    VALUES ($1, $2, $3, $4, NOW())
                    ON CONFLICT (data_type, timestamp) 
                    DO UPDATE SET 
                        data = EXCLUDED.data,
                        metadata = EXCLUDED.metadata,
                        updated_at = NOW()
                """, 
                    "global_stats",
                    row["timestamp"],
                    json.dumps(result),
                    json.dumps({"source": connector_id, "coins_count": None})
                )
                logger.debug(f"Saved global stats to visualization_data table")
            except Exception as save_err:
                logger.warning(f"Failed to save to visualization_data: {save_err}")
            
                logger.info(f"Returning global stats from database (timestamp: {row['timestamp']})")
                return JSONResponse(content=result)
                
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching global stats from database: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error fetching global stats: {str(e)}")


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
    """
    Fetch cryptocurrency market data from database.
    Data must first be persisted by backend scheduler (connector_id: coingecko_top).
    Enforces architecture: API → Database → Backend → Frontend.
    
    Reads normalized rows from database (one row per coin) and reconstructs the expected list format.
    Backend handles grouping, ordering, limiting, and aggregating before responding.
    """
    try:
        pool = get_pool()
        connector_id = "coingecko_top"
        
        async with pool.acquire() as conn:
            # Try visualization_data table first (optimized for visualization)
            viz_row = await conn.fetchrow("""
                SELECT data, timestamp, metadata
                FROM visualization_data
                WHERE data_type = 'markets'
                ORDER BY timestamp DESC
                LIMIT 1
            """)
            
            if viz_row:
                # Use visualization_data (already processed and ready)
                coins_list = viz_row["data"]
                if isinstance(coins_list, str):
                    try:
                        coins_list = json.loads(coins_list)
                    except:
                        pass
                
                if isinstance(coins_list, list) and len(coins_list) > 0:
                    latest_timestamp = viz_row["timestamp"]
                    # Filter by requested coin IDs if provided
                    if ids:
                        requested_ids = [id.strip().lower() for id in ids.split(",")]
                        coins_list = [
                            coin for coin in coins_list
                            if coin.get("id", "").lower() in requested_ids
                        ]
                    
                    # Normalize field names
                    for coin in coins_list:
                        if isinstance(coin, dict):
                            if "total_volume" in coin and "total_volume_24h" not in coin:
                                coin["total_volume_24h"] = coin["total_volume"]
                    
                    # Apply sorting
                    if order == "market_cap_desc":
                        coins_list.sort(key=lambda x: x.get("market_cap", 0) or 0, reverse=True)
                    elif order == "market_cap_asc":
                        coins_list.sort(key=lambda x: x.get("market_cap", 0) or 0, reverse=False)
                    elif order == "price_desc":
                        coins_list.sort(key=lambda x: x.get("current_price", 0) or 0, reverse=True)
                    elif order == "price_asc":
                        coins_list.sort(key=lambda x: x.get("current_price", 0) or 0, reverse=False)
                    
                    # Apply pagination
                    start_idx = (page - 1) * per_page
                    end_idx = start_idx + per_page
                    paginated_coins = coins_list[start_idx:end_idx]
                    
                    logger.info(f"Returning markets data from visualization_data (timestamp: {latest_timestamp}, coins: {len(coins_list)}, filtered: {len(paginated_coins)})")
                    response = JSONResponse(content=paginated_coins)
                    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
                    response.headers["Pragma"] = "no-cache"
                    response.headers["Expires"] = "0"
                    return response
            
            # Fallback to api_connector_data if visualization_data not available
            # Get the most recent timestamp to find all rows from the same batch
            latest_row = await conn.fetchrow("""
                SELECT timestamp
                FROM api_connector_data
                WHERE connector_id = $1
                ORDER BY timestamp DESC
                LIMIT 1
            """, connector_id)
            
            if not latest_row:
                raise HTTPException(
                    status_code=404,
                    detail=f"No data found for {connector_id}. Ensure the scheduler is running and has fetched data."
                )
            
            latest_timestamp = latest_row["timestamp"]
            
            # Get all rows from the most recent batch (within 1 second of latest timestamp)
            # This handles the case where list items are saved as separate rows
            # Calculate time bounds in Python to avoid PostgreSQL interval arithmetic issues
            from datetime import timedelta
            time_lower = latest_timestamp - timedelta(seconds=1)
            time_upper = latest_timestamp + timedelta(seconds=1)
            
            rows = await conn.fetch("""
                SELECT data, raw_response
                FROM api_connector_data
                WHERE connector_id = $1
                AND timestamp >= $2
                AND timestamp <= $3
                ORDER BY id
            """, connector_id, time_lower, time_upper)
            
            if not rows:
                raise HTTPException(
                    status_code=404,
                    detail=f"No data found for {connector_id}. Ensure the scheduler is running and has fetched data."
                )
            
            # Reconstruct the list by extracting coin data from each row
            # Handle both cases: 
            # 1. Multiple rows (one coin per row) - normalized storage
            # 2. Single row with full list in data field
            coins_list = []
            
            for row in rows:
                data = row["data"]
                raw_response = row.get("raw_response")
                
                # Handle string JSON (if stored as string)
                if isinstance(data, str):
                    try:
                        data = json.loads(data)
                    except:
                        pass
                
                if isinstance(raw_response, str):
                    try:
                        raw_response = json.loads(raw_response)
                    except:
                        pass
                
                # Priority 1: data is a list (entire list stored in one row)
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict):
                            # Validate it's a coin object
                            if item.get("id") or item.get("symbol") or item.get("name") or item.get("current_price") is not None:
                                coins_list.append(item)
                    continue
                
                # Priority 2: data is a dict
                if isinstance(data, dict):
                    # Check if this is a single coin object
                    if data.get("id") or data.get("symbol") or data.get("name") or data.get("current_price") is not None:
                        coins_list.append(data)
                        continue
                    # Check if data contains a nested list/array
                    elif "data" in data and isinstance(data["data"], list):
                        for item in data["data"]:
                            if isinstance(item, dict):
                                coins_list.append(item)
                        continue
                    # Check for other nested structures
                    elif any(isinstance(v, list) for v in data.values()):
                        for key, value in data.items():
                            if isinstance(value, list):
                                for item in value:
                                    if isinstance(item, dict) and (item.get("id") or item.get("symbol") or item.get("name")):
                                        coins_list.append(item)
                                break
                        continue
            
                # Priority 3: raw_response contains the data
                if raw_response:
                    if isinstance(raw_response, list):
                        for item in raw_response:
                            if isinstance(item, dict) and (item.get("id") or item.get("symbol") or item.get("name") or item.get("current_price") is not None):
                                coins_list.append(item)
                        continue
                    elif isinstance(raw_response, dict):
                        # Check if it's a single coin
                        if raw_response.get("id") or raw_response.get("symbol") or raw_response.get("name") or raw_response.get("current_price") is not None:
                            coins_list.append(raw_response)
                            continue
                        # Check if it contains a list
                        elif "data" in raw_response and isinstance(raw_response["data"], list):
                            for item in raw_response["data"]:
                                if isinstance(item, dict):
                                    coins_list.append(item)
                            continue
                        # Check for nested lists
                    elif any(isinstance(v, list) for v in raw_response.values()):
                            for key, value in raw_response.items():
                                if isinstance(value, list):
                                    for item in value:
                                        if isinstance(item, dict) and (item.get("id") or item.get("symbol") or item.get("name")):
                                            coins_list.append(item)
                                break
                            continue
            
            if not coins_list or len(coins_list) == 0:
                # Try to read from visualization_data table as fallback
                try:
                    viz_row = await conn.fetchrow("""
                        SELECT data, timestamp
                        FROM visualization_data
                        WHERE data_type = 'markets'
                        ORDER BY timestamp DESC
                        LIMIT 1
                    """)
                    
                    if viz_row and viz_row.get("data"):
                        viz_data = viz_row["data"]
                        if isinstance(viz_data, list):
                            coins_list = viz_data
                            logger.info(f"Using fallback: loaded {len(coins_list)} coins from visualization_data table")
                        elif isinstance(viz_data, dict) and "data" in viz_data and isinstance(viz_data["data"], list):
                            coins_list = viz_data["data"]
                            logger.info(f"Using fallback: loaded {len(coins_list)} coins from visualization_data table")
                except Exception as viz_err:
                    logger.debug(f"Could not read from visualization_data: {viz_err}")
                
                # If still no coins, log detailed error
                if not coins_list or len(coins_list) == 0:
                    # Log detailed information for debugging
                    sample_data = None
                    sample_raw = None
                    data_type = None
                    if rows:
                        first_row = rows[0]
                        data_type = type(first_row.get("data")).__name__
                        data_val = first_row.get("data")
                        if data_val:
                            if isinstance(data_val, str):
                                sample_data = data_val[:500]
                            else:
                                sample_data = str(data_val)[:500]
                        raw_val = first_row.get("raw_response")
                        if raw_val:
                            if isinstance(raw_val, str):
                                sample_raw = raw_val[:500]
                            else:
                                sample_raw = str(raw_val)[:500]
                    
                    logger.error(
                        f"Could not reconstruct coins list for {connector_id}. "
                        f"Found {len(rows)} rows but extracted 0 coins. "
                        f"Data type: {data_type}, "
                        f"Sample data preview: {sample_data}, "
                        f"Sample raw_response preview: {sample_raw}"
                    )
                raise HTTPException(
                    status_code=500,
                        detail=f"Could not reconstruct coins list from database. "
                               f"Found {len(rows)} rows but extracted 0 coins. "
                               f"Data format may be unexpected. Check logs for details."
                )
            
            # Filter by requested coin IDs if provided
            if ids:
                requested_ids = [id.strip().lower() for id in ids.split(",")]
                coins_list = [
                    coin for coin in coins_list
                    if coin.get("id", "").lower() in requested_ids
                ]
            
            # Normalize field names - CoinGecko uses 'total_volume' but frontend expects 'total_volume_24h'
            for coin in coins_list:
                if isinstance(coin, dict):
                    if "total_volume" in coin and "total_volume_24h" not in coin:
                        coin["total_volume_24h"] = coin["total_volume"]
            
            # Apply sorting
            if order == "market_cap_desc":
                coins_list.sort(key=lambda x: x.get("market_cap", 0) or 0, reverse=True)
            elif order == "market_cap_asc":
                coins_list.sort(key=lambda x: x.get("market_cap", 0) or 0, reverse=False)
            elif order == "price_desc":
                coins_list.sort(key=lambda x: x.get("current_price", 0) or 0, reverse=True)
            elif order == "price_asc":
                coins_list.sort(key=lambda x: x.get("current_price", 0) or 0, reverse=False)
            
            # Apply pagination
            start_idx = (page - 1) * per_page
            end_idx = start_idx + per_page
            paginated_coins = coins_list[start_idx:end_idx]
            
            # Save full coins list to visualization_data table for easy monitoring
            # Store the complete list (before pagination) for monitoring purposes
            try:
                await conn.execute("""
                    INSERT INTO visualization_data (data_type, timestamp, data, metadata, updated_at)
                    VALUES ($1, $2, $3, $4, NOW())
                    ON CONFLICT (data_type, timestamp) 
                    DO UPDATE SET 
                        data = EXCLUDED.data,
                        metadata = EXCLUDED.metadata,
                        updated_at = NOW()
                """, 
                    "markets",
                    latest_timestamp,
                    json.dumps(coins_list),  # Store full list
                    json.dumps({
                        "source": connector_id,
                        "total_coins": len(coins_list),
                        "filtered_coins": len(paginated_coins),
                        "page": page,
                        "per_page": per_page
                    })
                )
                logger.debug(f"Saved markets data to visualization_data table ({len(coins_list)} coins)")
            except Exception as save_err:
                logger.warning(f"Failed to save to visualization_data: {save_err}")
            
            logger.info(f"Returning markets data from database (timestamp: {latest_timestamp}, rows: {len(rows)}, coins: {len(coins_list)}, filtered: {len(paginated_coins)})")
            return JSONResponse(content=paginated_coins)
                
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching markets from database: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching markets: {str(e)}")


# Diagnostic endpoint to inspect raw data storage
@app.get("/api/crypto/debug/{connector_id}")
async def debug_connector_data(connector_id: str):
    """
    Debug endpoint to inspect how data is stored in the database.
    Useful for troubleshooting data format issues.
    """
    try:
        pool = get_pool()
        
        async with pool.acquire() as conn:
            # Get the most recent rows
            rows = await conn.fetch("""
                SELECT id, timestamp, data, raw_response, 
                       pg_typeof(data) as data_type,
                       pg_typeof(raw_response) as raw_response_type
                FROM api_connector_data
                WHERE connector_id = $1
                ORDER BY timestamp DESC
                LIMIT 5
            """, connector_id)
            
            if not rows:
                return {
                    "connector_id": connector_id,
                    "message": "No data found",
                    "rows": []
                }
            
            result = []
            for row in rows:
                data = row["data"]
                raw_response = row.get("raw_response")
                
                # Get type information
                data_type = type(data).__name__
                if isinstance(data, str):
                    try:
                        parsed = json.loads(data)
                        data_type += f" (parses to {type(parsed).__name__})"
                    except:
                        data_type += " (invalid JSON)"
                
                result.append({
                    "id": row["id"],
                    "timestamp": row["timestamp"].isoformat() if row["timestamp"] else None,
                    "data_type": data_type,
                    "data_preview": str(data)[:200] if data else None,
                    "data_is_list": isinstance(data, list),
                    "data_is_dict": isinstance(data, dict),
                    "data_is_string": isinstance(data, str),
                    "raw_response_type": type(raw_response).__name__ if raw_response else None,
                    "raw_response_preview": str(raw_response)[:200] if raw_response else None,
                })
            
            return {
                "connector_id": connector_id,
                "total_rows": len(rows),
                "rows": result
            }
    
    except Exception as e:
        logger.error(f"Error in debug endpoint: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# Visualization Data Monitoring Endpoints
@app.get("/api/visualization/data")
async def get_visualization_data(
    data_type: Optional[str] = Query(None, description="Filter by data type: 'markets' or 'global_stats'"),
    limit: int = Query(10, description="Number of recent records to return"),
    skip: int = Query(0, description="Number of records to skip")
):
    """
    Get visualization data from the dedicated visualization_data table.
    Useful for monitoring and debugging visualization data storage.
    """
    try:
        pool = get_pool()
        
        async with pool.acquire() as conn:
            query = """
                SELECT id, data_type, timestamp, data, metadata, created_at, updated_at
                FROM visualization_data
            """
            params = []
            
            if data_type:
                query += " WHERE data_type = $1"
                params.append(data_type)
            
            query += " ORDER BY timestamp DESC LIMIT $%d OFFSET $%d" % (len(params) + 1, len(params) + 2)
            params.extend([limit, skip])
            
            rows = await conn.fetch(query, *params)
            
            # Get total count
            count_query = "SELECT COUNT(*) FROM visualization_data"
            if data_type:
                count_query += " WHERE data_type = $1"
                total_count = await conn.fetchval(count_query, data_type)
            else:
                total_count = await conn.fetchval(count_query)
            
            result = []
            for row in rows:
                result.append({
                    "id": row["id"],
                    "data_type": row["data_type"],
                    "timestamp": row["timestamp"].isoformat() if row["timestamp"] else None,
                    "data": row["data"],
                    "metadata": row["metadata"],
                    "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                    "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None
                })
            
            return {
                "success": True,
                "data": result,
                "total": total_count,
                "limit": limit,
                "skip": skip
            }
    
    except Exception as e:
        logger.error(f"Error fetching visualization data: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error fetching visualization data: {str(e)}")


@app.post("/api/visualization/trigger-update")
async def trigger_visualization_update(connector_id: str = "coingecko_top"):
    """
    Manually trigger visualization_data update for testing.
    This endpoint reads the latest data from api_connector_data and updates visualization_data.
    """
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            if connector_id == "coingecko_top":
                # Get latest timestamp
                latest_row = await conn.fetchrow("""
                    SELECT timestamp
                    FROM api_connector_data
                    WHERE connector_id = $1
                    ORDER BY timestamp DESC
                    LIMIT 1
                """, connector_id)
                
                if not latest_row:
                    raise HTTPException(status_code=404, detail=f"No data found for {connector_id}")
                
                latest_timestamp = latest_row["timestamp"]
                from datetime import timedelta
                time_lower = latest_timestamp - timedelta(seconds=2)
                time_upper = latest_timestamp + timedelta(seconds=2)
                
                # Get all rows from latest batch
                rows = await conn.fetch("""
                    SELECT data, raw_response, timestamp
                    FROM api_connector_data
                    WHERE connector_id = $1
                    AND timestamp >= $2
                    AND timestamp <= $3
                    ORDER BY id
                """, connector_id, time_lower, time_upper)
                
                if not rows:
                    raise HTTPException(status_code=404, detail=f"No rows found for {connector_id}")
                
                # Use the first row's data
                first_row = rows[0]
                data = first_row["data"]
                raw_response = first_row.get("raw_response")
                timestamp = first_row["timestamp"]
                
                # Trigger update
                await update_visualization_data(connector_id, data, timestamp, raw_response)
                
                return {"status": "success", "message": f"Visualization data updated for {connector_id}", "rows_processed": len(rows)}
            
            elif connector_id == "coingecko_global":
                row = await conn.fetchrow("""
                    SELECT data, raw_response, timestamp
                    FROM api_connector_data
                    WHERE connector_id = $1
                    ORDER BY timestamp DESC
                    LIMIT 1
                """, connector_id)
                
                if not row:
                    raise HTTPException(status_code=404, detail=f"No data found for {connector_id}")
                
                await update_visualization_data(connector_id, row["data"], row["timestamp"], row.get("raw_response"))
                
                return {"status": "success", "message": f"Visualization data updated for {connector_id}"}
            else:
                raise HTTPException(status_code=400, detail=f"Unsupported connector_id: {connector_id}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error triggering visualization update: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/visualization/data/latest")
async def get_latest_visualization_data(
    data_type: str = Query(..., description="Data type: 'markets' or 'global_stats'")
):
    """
    Get the most recent visualization data for a specific type.
    """
    try:
        pool = get_pool()
        
        async with pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT id, data_type, timestamp, data, metadata, created_at, updated_at
                FROM visualization_data
                WHERE data_type = $1
                ORDER BY timestamp DESC
                LIMIT 1
            """, data_type)
            
            if not row:
                raise HTTPException(
                    status_code=404,
                    detail=f"No visualization data found for type: {data_type}"
                )
            
            return {
                "success": True,
                "data": {
                    "id": row["id"],
                    "data_type": row["data_type"],
                    "timestamp": row["timestamp"].isoformat() if row["timestamp"] else None,
                    "data": row["data"],
                    "metadata": row["metadata"],
                    "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                    "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None
                }
            }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching latest visualization data: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching latest visualization data: {str(e)}")


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


async def save_websocket_to_db(message: dict) -> Optional[Dict[str, Any]]:
    """
    Helper function to save WebSocket message to database (for use by WebSocket stream manager)
    Returns database record with id, source_id, session_id, etc.
    """
    try:
        pool = get_pool()
        raw_data = message.get("data", {})
        exchange = message.get("exchange", "custom")
        instrument = message.get("instrument") or "-"
        price = message.get("price") or 0.0
        message_type = message.get("message_type", "trade")
        timestamp_str = message.get("timestamp")
        
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
        source_id = hashlib.md5(f"{message.get('connector_id', 'unknown')}_{timestamp}_{json.dumps(raw_data)}".encode()).hexdigest()[:16]
        session_id = message.get("session_id", str(uuid.uuid4()))
        
        async with pool.acquire() as conn:
            inserted_id = await conn.fetchval("""
                INSERT INTO websocket_messages (
                    timestamp, exchange, instrument, price, data, message_type
                ) VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id
            """,
                timestamp,
                exchange,
                instrument,
                price,
                json.dumps(raw_data),
                message_type
            )
            
            return {
                "id": inserted_id,
                "source_id": source_id,
                "session_id": session_id,
                "connector_id": message.get("connector_id", "unknown"),
                "timestamp": timestamp.isoformat(),
                "exchange": exchange,
                "instrument": instrument,
                "price": price
            }
    except Exception as e:
        logger.error(f"Error saving WebSocket message to database: {e}")
        import traceback
        traceback.print_exc()
        return None


# Initialize WebSocket Stream Manager (persistence-first)
websocket_stream_manager = WebSocketStreamManager(
    db_save_callback=save_websocket_to_db,
    broadcast_callback=broadcast_to_websocket
)


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
            
            # Update api_connectors status to 'running' (also done in connector_manager, but ensure it's set)
            async with pool.acquire() as conn:
                await conn.execute("""
                    UPDATE api_connectors 
                    SET status = 'running', updated_at = NOW()
                    WHERE connector_id = $1
                """, connector_id)
            
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
        
        # Update api_connectors status to 'inactive' (also done in connector_manager, but ensure it's set)
        pool = get_pool()
        async with pool.acquire() as conn:
            await conn.execute("""
                UPDATE api_connectors 
                SET status = 'inactive', updated_at = NOW()
                WHERE connector_id = $1
            """, connector_id)
        
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


@app.get("/api/pipeline")
async def list_pipelines():
    """List distinct pipeline API ids with latest run metadata."""
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT DISTINCT ON (api_id)
                    api_id,
                    api_name,
                    api_type,
                    source_url,
                    destination,
                    status,
                    started_at,
                    completed_at,
                    next_run_at,
                    last_run_at
                FROM pipeline_runs
                ORDER BY api_id, started_at DESC
                """
            )
        if rows and len(rows) > 0:
            return [dict(r) for r in rows]

        # Fallback: expose active connectors even if no pipeline_runs exist yet
        async with pool.acquire() as conn:
            fallback_rows = await conn.fetch(
                """
                SELECT connector_id AS api_id,
                       name AS api_name,
                       'non-realtime' AS api_type,
                       api_url AS source_url,
                       'postgres/api_connector_data' AS destination,
                       status,
                       NOW() AS started_at,
                       NULL::timestamp AS completed_at,
                       NULL::timestamp AS next_run_at,
                       NULL::timestamp AS last_run_at
                FROM api_connectors
                ORDER BY connector_id
                """
            )
        return [dict(r) for r in fallback_rows]
    except Exception as e:
        logger.error(f"[PIPELINE] Failed to list pipelines: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/pipeline/{api_id}")
async def get_pipeline_view(api_id: str):
    """Return live pipeline state for a scheduled API run plus recent history."""
    try:
        pipeline_state = await get_pipeline_state(api_id)
        active_run = pipeline_state.get("active_run")
        steps = pipeline_state.get("steps", [])
        latest_steps = pipeline_state.get("latest_steps", [])
        history = pipeline_state.get("history", [])

        display_steps = steps if active_run else latest_steps
        display_run = active_run
        if not display_run and history:
            display_run = history[0]
        if not display_run and not history:
            # Graceful empty response when no runs exist yet for this API
            return {
                "api": {"api_id": api_id},
                "current_run": None,
                "history": [],
                "active": False,
            }

        total_steps = len(display_steps) or 1
        completed_steps = len([s for s in display_steps if s.get("status") == "success"])
        progress_pct = int((completed_steps / total_steps) * 100)

        api_meta = {
            "api_id": display_run.get("api_id") if display_run else api_id,
            "api_name": display_run.get("api_name") if display_run else None,
            "api_type": display_run.get("api_type") if display_run else None,
            "source_url": display_run.get("source_url") if display_run else None,
            "destination": display_run.get("destination") if display_run else None,
            "schedule": {
                "cron": display_run.get("schedule_cron") if display_run else None,
                "interval_seconds": display_run.get("schedule_interval_seconds") if display_run else None,
                "last_run": display_run.get("last_run_at") if display_run else None,
                "next_run": display_run.get("next_run_at") if display_run else None,
            },
        }

        current_run = None
        if display_run:
            current_run = {
                "run_id": display_run.get("id"),
                "status": display_run.get("status"),
                "started_at": display_run.get("started_at"),
                "completed_at": display_run.get("completed_at"),
                "next_run_at": display_run.get("next_run_at"),
                "error_message": display_run.get("error_message"),
                "progress_pct": progress_pct,
                "steps": display_steps,
            }

        run_history = []
        for row in history:
            duration = None
            if row.get("started_at") and row.get("completed_at"):
                duration = (row.get("completed_at") - row.get("started_at")).total_seconds()
            run_history.append(
                {
                    "run_id": row.get("id"),
                    "status": row.get("status"),
                    "started_at": row.get("started_at"),
                    "completed_at": row.get("completed_at"),
                    "duration_seconds": duration,
                    "next_run_at": row.get("next_run_at"),
                    "error_message": row.get("error_message"),
                    "steps": row.get("steps", []),  # Include steps for each history run
                }
            )

        return {
            "api": api_meta,
            "current_run": current_run,
            "history": run_history,
            "active": bool(active_run),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[PIPELINE] Failed to fetch pipeline for {api_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/pipeline/{api_id}/failed-calls")
async def get_failed_api_calls_for_pipeline(api_id: str, limit: int = 100):
    """Get failed API calls for a specific pipeline/API."""
    try:
        failed_calls = await get_failed_api_calls(api_id=api_id, limit=limit)
        return {
            "api_id": api_id,
            "failed_calls": failed_calls,
            "count": len(failed_calls),
        }
    except Exception as e:
        logger.error(f"[FAILED_API] Failed to fetch failed API calls for {api_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/pipeline/failed-calls/all")
async def get_all_failed_api_calls(limit: int = 200):
    """Get all failed API calls across all pipelines/APIs."""
    try:
        failed_calls = await get_failed_api_calls(api_id=None, limit=limit)
        return {
            "failed_calls": failed_calls,
            "count": len(failed_calls),
        }
    except Exception as e:
        logger.error(f"[FAILED_API] Failed to fetch all failed API calls: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/etl/active")
async def list_active_etl_apis(lookback_minutes: int = 90):
    """
    List active scheduled APIs with their latest activity.
    Uses pipeline_steps table as the primary source of truth for counts.
    Falls back to calculating from tables if pipeline_steps record is missing.
    """
    try:
        pool = get_pool()
        cutoff = datetime.utcnow() - timedelta(minutes=lookback_minutes)
        async with pool.acquire() as conn:
            # Fetch pipeline steps for fast lookup
            pipeline_steps_map = {}
            try:
                steps = await conn.fetch("SELECT * FROM pipeline_steps")
                for step in steps:
                    pipeline_steps_map[step['pipeline_name']] = dict(step)
            except Exception as e:
                logger.warning(f"Could not fetch pipeline_steps: {e}")

            connectors = await conn.fetch(
                """
                SELECT connector_id, name, api_url, polling_interval, status, exchange_name
                FROM api_connectors
                WHERE status IN ('active', 'running', 'started', 'enabled')
                ORDER BY connector_id
                """
            )

            results = []
            for row in connectors:
                row_dict = dict(row)
                connector_id = row_dict["connector_id"]
                
                # Get latest activity timestamps (still useful for liveness check)
                last_data = await conn.fetchrow(
                    """
                    SELECT timestamp, status_code, response_time_ms
                    FROM api_connector_data
                    WHERE connector_id = $1
                    ORDER BY timestamp DESC
                    LIMIT 1
                    """,
                    connector_id,
                )
                last_item = await conn.fetchrow(
                    """
                    SELECT timestamp
                    FROM api_connector_items
                    WHERE connector_id = $1
                    ORDER BY timestamp DESC
                    LIMIT 1
                    """,
                    connector_id,
                )
                
                # Get counts - prefer pipeline_steps, fallback to slow COUNT(*)
                if connector_id in pipeline_steps_map:
                    step_info = pipeline_steps_map[connector_id]
                    total_data = step_info.get('extract_count', 0)
                    total_items = step_info.get('transform_count', 0)
                    # Use status from pipeline_steps if available? 
                    # User said "Status should change automatically: PENDING -> RUNNING -> COMPLETED"
                    # But the connector status in api_connectors is 'active'. 
                    # We might want to show the pipeline status too, but this endpoint returns connector status.
                    # We'll stick to counts for now to avoid breaking frontend.
                else:
                    totals = await conn.fetchrow(
                        """
                        SELECT 
                            (SELECT COUNT(*) FROM api_connector_data WHERE connector_id = $1) AS total_data,
                            (SELECT COUNT(*) FROM api_connector_items WHERE connector_id = $1) AS total_items
                        """,
                        connector_id,
                    )
                    totals_dict = dict(totals) if totals else {}
                    total_data = totals_dict.get("total_data", 0)
                    total_items = totals_dict.get("total_items", 0)

                last_ts_candidates = []
                if last_data and dict(last_data).get("timestamp"):
                    last_ts_candidates.append(dict(last_data).get("timestamp"))
                if last_item and dict(last_item).get("timestamp"):
                    last_ts_candidates.append(dict(last_item).get("timestamp"))
                last_ts = max(last_ts_candidates) if last_ts_candidates else None

                # Treat scheduler-managed APIs as ACTIVE as long as connector exists
                status_label = "ACTIVE"

                last_data_dict = dict(last_data) if last_data else {}

                results.append(
                    {
                        "connector_id": connector_id,
                        "name": row_dict.get("name"),
                        "api_url": row_dict.get("api_url"),
                        "exchange_name": row_dict.get("exchange_name"),
                        "polling_interval": row_dict.get("polling_interval"),
                        "status": status_label,
                        "last_timestamp": last_ts,
                        "last_status_code": last_data_dict.get("status_code") if last_data_dict else None,
                        "last_response_time_ms": float(last_data_dict.get("response_time_ms"))
                        if last_data_dict and last_data_dict.get("response_time_ms") is not None
                        else None,
                        "total_records": total_data,
                        "total_items": total_items,
                    }
                )

        return results
    except Exception as e:
        logger.error(f"[PIPELINE] Failed to list active ETL APIs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/pipeline/steps")
async def get_pipeline_steps():
    """
    Get current state of all ETL pipelines from the single source of truth table.
    This endpoint reads ONLY from the database (pipeline_steps table).
    """
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            # Check if table exists first to avoid 500 error during migration
            table_exists = await conn.fetchval(
                "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'pipeline_steps')"
            )
            if not table_exists:
                return []
                
            steps = await conn.fetch("SELECT * FROM pipeline_steps ORDER BY pipeline_name")
            
            # Convert to list of dicts and handle datetime serialization
            results = []
            for step in steps:
                step_dict = dict(step)
                if step_dict.get('last_run_at'):
                    step_dict['last_run_at'] = step_dict['last_run_at'].isoformat()
                if step_dict.get('created_at'):
                    step_dict['created_at'] = step_dict['created_at'].isoformat()
                results.append(step_dict)
                
            return results
    except Exception as e:
        logger.error(f"Failed to fetch pipeline steps: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/etl/pipeline/{connector_id}")
async def get_etl_pipeline_history(connector_id: str, history_limit: int = 15):
    """
    Return ETL pipeline view + recent history using existing pipeline tables
    and activity from api_connector_data/api_connector_items.
    """
    try:
        pipeline_state = await get_pipeline_state(connector_id, history_limit=history_limit)
        active_run = pipeline_state.get("active_run")
        steps = pipeline_state.get("steps", [])
        latest_steps = pipeline_state.get("latest_steps", [])
        history = pipeline_state.get("history", [])

        display_steps = steps if active_run else latest_steps
        display_run = active_run or (history[0] if history else None)

        if display_run:
            total_steps = len(display_steps) or 1
            completed_steps = len([s for s in display_steps if s.get("status") == "success"])
            progress_pct = int((completed_steps / total_steps) * 100)
        else:
            progress_pct = 0

        api_meta = {
            "api_id": connector_id,
            "api_name": display_run.get("api_name") if display_run else None,
            "api_type": display_run.get("api_type") if display_run else None,
            "source_url": display_run.get("source_url") if display_run else None,
            "destination": display_run.get("destination") if display_run else "postgres/api_connector_data",
            "schedule": {
                "cron": display_run.get("schedule_cron") if display_run else None,
                "interval_seconds": display_run.get("schedule_interval_seconds") if display_run else None,
                "last_run": display_run.get("last_run_at") if display_run else None,
                "next_run": display_run.get("next_run_at") if display_run else None,
            },
        }

        current_run = None
        if display_run:
            current_run = {
                "run_id": display_run.get("id"),
                "status": display_run.get("status"),
                "started_at": display_run.get("started_at"),
                "completed_at": display_run.get("completed_at"),
                "next_run_at": display_run.get("next_run_at"),
                "error_message": display_run.get("error_message"),
                "progress_pct": progress_pct,
                "steps": display_steps,
            }

        run_history = []
        for row in history:
            duration = None
            if row.get("started_at") and row.get("completed_at"):
                duration = (row.get("completed_at") - row.get("started_at")).total_seconds()
            run_history.append(
                {
                    "run_id": row.get("id"),
                    "status": row.get("status"),
                    "started_at": row.get("started_at"),
                    "completed_at": row.get("completed_at"),
                    "duration_seconds": duration,
                    "next_run_at": row.get("next_run_at"),
                    "error_message": row.get("error_message"),
                    "steps": row.get("steps", []),  # Include steps for each history run
                }
            )

        pool = get_pool()
        async with pool.acquire() as conn:
            # First, ensure counts are up-to-date by updating pipeline_steps
            try:
                await update_pipeline_counts(connector_id)
            except Exception as update_err:
                logger.warning(f"[PIPELINE] Could not update counts before fetching pipeline state: {update_err}")
            
            # Get counts from pipeline_steps (single source of truth) for consistency with summary cards
            pipeline_step = await conn.fetchrow(
                """
                SELECT extract_count, transform_count, load_count, last_run_at
                FROM pipeline_steps
                WHERE pipeline_name = $1
                """,
                connector_id,
            )
            
            # Fallback to direct calculation if pipeline_steps doesn't exist
            if pipeline_step:
                total_data = pipeline_step.get('extract_count', 0) or 0
                total_items = pipeline_step.get('transform_count', 0) or 0
            else:
                # Calculate directly from tables as fallback
                counts = await conn.fetchrow(
                    """
                    SELECT 
                        COUNT(*) AS total_data,
                        MAX(timestamp) AS last_data_at
                    FROM api_connector_data
                    WHERE connector_id = $1
                    """,
                    connector_id,
                )
                item_counts = await conn.fetchrow(
                    """
                    SELECT 
                        COUNT(*) AS total_items,
                        MAX(timestamp) AS last_item_at
                    FROM api_connector_items
                    WHERE connector_id = $1
                    """,
                    connector_id,
                )
                counts_dict = dict(counts) if counts else {}
                item_counts_dict = dict(item_counts) if item_counts else {}
                total_data = counts_dict.get("total_data", 0) or 0
                total_items = item_counts_dict.get("total_items", 0) or 0
            
            # Get last timestamps for activity tracking
            counts = await conn.fetchrow(
                """
                SELECT 
                    MAX(timestamp) AS last_data_at
                FROM api_connector_data
                WHERE connector_id = $1
                """,
                connector_id,
            )
            item_counts = await conn.fetchrow(
                """
                SELECT 
                    MAX(timestamp) AS last_item_at
                FROM api_connector_items
                WHERE connector_id = $1
                """,
                connector_id,
            )
            activity_rows = await conn.fetch(
                """
                SELECT id, timestamp, status_code, response_time_ms, message_type
                FROM api_connector_data
                WHERE connector_id = $1
                ORDER BY timestamp DESC
                LIMIT 15
                """,
                connector_id,
            )
            latest_data_rows = await conn.fetch(
                """
                SELECT id, timestamp, data, raw_response, status_code, response_time_ms
                FROM api_connector_data
                WHERE connector_id = $1
                ORDER BY timestamp DESC
                LIMIT 20
                """,
                connector_id,
            )

        def _map_activity(row):
            row_dict = dict(row)
            return {
                "id": row_dict.get("id"),
                "timestamp": row_dict.get("timestamp"),
                "status_code": row_dict.get("status_code"),
                "response_time_ms": float(row_dict.get("response_time_ms"))
                if row_dict.get("response_time_ms") is not None
                else None,
                "message_type": row_dict.get("message_type"),
            }

        counts_dict = dict(counts) if counts else {}
        item_counts_dict = dict(item_counts) if item_counts else {}

        data_stats = {
            "total_records": total_data,  # Use from pipeline_steps for consistency
            "last_data_at": counts_dict.get("last_data_at"),
            "total_items": total_items,  # Use from pipeline_steps for consistency
            "last_item_at": item_counts_dict.get("last_item_at"),
        }

        def _map_latest(row):
            row_dict = dict(row)
            return {
                "id": row_dict.get("id"),
                "timestamp": row_dict.get("timestamp"),
                "status_code": row_dict.get("status_code"),
                "response_time_ms": float(row_dict.get("response_time_ms"))
                if row_dict.get("response_time_ms") is not None
                else None,
                "data": row_dict.get("data"),
                "raw_response": row_dict.get("raw_response"),
            }

        return {
            "api": api_meta,
            "current_run": current_run,
            "history": run_history,
            "active": bool(active_run),
            "data_stats": data_stats,
            "activity_log": [_map_activity(r) for r in activity_rows] if activity_rows else [],
            "latest_data": [_map_latest(r) for r in latest_data_rows] if latest_data_rows else [],
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[PIPELINE] Failed to build ETL history for {connector_id}: {e}")
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


# ==================== WebSocket Stream Management Endpoints (Persistence-First) ====================

class WebSocketConnectRequest(BaseModel):
    exchange: str  # 'okx', 'binance', or 'custom'
    websocket_url: Optional[str] = None
    subscription_message: Optional[Dict[str, Any]] = None
    channel: Optional[str] = None  # For OKX
    inst_id: Optional[str] = None  # For OKX
    symbol: Optional[str] = None  # For Binance
    stream_type: Optional[str] = None  # For Binance


@app.post("/api/websocket/connect")
async def connect_websocket_stream(request: WebSocketConnectRequest):
    """
    Connect to external WebSocket stream with persistence-first flow.
    All data is saved to database before being broadcast to frontend.
    """
    try:
        connection_id = f"ws_{uuid.uuid4().hex[:12]}"
        exchange = request.exchange.lower()
        
        # Determine WebSocket URL based on exchange
        websocket_url = request.websocket_url
        
        if exchange == "okx":
            if not websocket_url:
                websocket_url = "wss://ws.okx.com:8443/ws/v5/public"
            
            # Build subscription message for OKX
            subscription_message = request.subscription_message
            if not subscription_message:
                channel = request.channel or "trades"
                inst_id = request.inst_id or "BTC-USDT"
                
                if inst_id == "ALL":
                    # Cap to avoid oversized subscription
                    inst_ids = [
                        'BTC-USDT', 'ETH-USDT', 'BNB-USDT', 'SOL-USDT', 'XRP-USDT',
                        'ADA-USDT', 'DOGE-USDT', 'MATIC-USDT', 'DOT-USDT', 'AVAX-USDT'
                    ]
                    subscription_message = {
                        "op": "subscribe",
                        "args": [{"channel": channel, "instId": inst} for inst in inst_ids]
                    }
                else:
                    subscription_message = {
                        "op": "subscribe",
                        "args": [{"channel": channel, "instId": inst_id}]
                    }
        
        elif exchange == "binance":
            if not websocket_url:
                symbol = request.symbol or "BTCUSDT"
                stream_type = request.stream_type or "trade"
                
                if symbol == "ALL":
                    # Use combined stream endpoint
                    streams = [
                        f"btcusdt@{stream_type}", f"ethusdt@{stream_type}",
                        f"bnbusdt@{stream_type}", f"solusdt@{stream_type}",
                        f"xrpusdt@{stream_type}"
                    ]
                    websocket_url = f"wss://stream.binance.com:9443/stream?streams={'/'.join(streams)}"
                else:
                    stream_name = f"{symbol.lower()}@{stream_type}"
                    websocket_url = f"wss://stream.binance.com:9443/ws/{stream_name}"
            
            subscription_message = None  # Binance doesn't need subscription message
        
        elif exchange == "custom":
            if not websocket_url:
                raise HTTPException(status_code=400, detail="websocket_url is required for custom exchange")
            subscription_message = request.subscription_message
        
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported exchange: {exchange}")
        
        # Connect via WebSocket Stream Manager (persistence-first)
        result = await websocket_stream_manager.connect(
            connection_id=connection_id,
            websocket_url=websocket_url,
            exchange=exchange,
            subscription_message=subscription_message,
            channel=request.channel,
            inst_id=request.inst_id,
            symbol=request.symbol,
            stream_type=request.stream_type
        )
        
        if result.get("success"):
            return {
                "success": True,
                "connection_id": connection_id,
                "exchange": exchange,
                "websocket_url": websocket_url,
                "message": "WebSocket stream connected. Data will be persisted to database before visualization."
            }
        else:
            raise HTTPException(status_code=500, detail=result.get("error", "Failed to connect"))
    
    except Exception as e:
        logger.error(f"Error connecting WebSocket stream: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/websocket/disconnect/{connection_id}")
async def disconnect_websocket_stream(connection_id: str):
    """Disconnect external WebSocket stream"""
    try:
        result = await websocket_stream_manager.disconnect(connection_id)
        
        if result.get("success"):
            return {
                "success": True,
                "connection_id": connection_id,
                "message": "WebSocket stream disconnected"
            }
        else:
            raise HTTPException(status_code=404, detail=result.get("error", "Connection not found"))
    
    except Exception as e:
        logger.error(f"Error disconnecting WebSocket stream: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/websocket/connections")
async def list_websocket_connections():
    """List all active WebSocket stream connections"""
    try:
        connections = websocket_stream_manager.list_connections()
        return {
            "success": True,
            "connections": connections,
            "count": len(connections)
        }
    except Exception as e:
        logger.error(f"Error listing WebSocket connections: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/websocket/connections/{connection_id}")
async def get_websocket_connection_status(connection_id: str):
    """Get status of a specific WebSocket stream connection"""
    try:
        status = websocket_stream_manager.get_connection_status(connection_id)
        
        if status:
            return {
                "success": True,
                "connection": status
            }
        else:
            raise HTTPException(status_code=404, detail="Connection not found")
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting WebSocket connection status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.websocket("/api/realtime")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time data updates to UI (receives persisted data from backend)"""
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
    """Upload a file (CSV, JSON, or XLSX) - saved in organized folders by type"""
    try:
        # Validate file type (fallback to content-type if extension missing)
        allowed_types = {'csv', 'json', 'xlsx', 'xls'}
        file_ext = file.filename.split('.')[-1].lower() if '.' in file.filename else ''
        if file_ext not in allowed_types:
            # Try content-type mapping when extension is absent or unexpected
            ct = (file.content_type or "").lower()
            if 'json' in ct:
                file_ext = 'json'
            elif 'csv' in ct:
                file_ext = 'csv'
            elif 'spreadsheet' in ct or 'excel' in ct:
                file_ext = 'xlsx'

        if file_ext not in allowed_types:
            raise HTTPException(status_code=400, detail=f"Unsupported file type: {file_ext or file.content_type}. Supported types: CSV, JSON, XLSX")
        
        # Generate unique file ID
        file_id = str(uuid.uuid4())
        
        # Get appropriate directory based on file type
        uploads_type_dir = get_uploads_dir_by_type(file_ext)
        safe_name = file.filename or f"upload.{file_ext}"
        file_path = uploads_type_dir / f"{file_id}_{safe_name}"
        
        # Save uploaded file
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Persist metadata in database so uploads are traceable
        try:
            db_record_id = await save_uploaded_file_metadata(
                file_id=file_id,
                filename=safe_name,
                file_type=file.content_type or file_ext,
                file_size=file_path.stat().st_size,
                storage_path=str(file_path),
                status="uploaded",
            )
        except Exception as db_err:
            logger.error(f"[FILE UPLOAD] Failed to record upload in DB: {db_err}")
            # Remove the saved file so disk and DB stay consistent
            try:
                file_path.unlink(missing_ok=True)
            except Exception:
                pass
            raise HTTPException(status_code=500, detail="Could not save upload metadata")
        
        # Determine source type
        source_type = 'xlsx' if file_ext in ['xlsx', 'xls'] else file_ext
        
        logger.info(f"[FILE UPLOAD] Uploaded {file.filename} (ID: {file_id}) to {uploads_type_dir}")
        
        return {
            "file_id": file_id,
            "filename": file.filename,
            "file_path": str(file_path),
            "source_type": source_type,
            "file_type": file_ext,
            "record_id": db_record_id,
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
        
        # Search in all upload type directories
        uploaded_files = []
        for uploads_subdir in [UPLOADS_CSV_DIR, UPLOADS_JSON_DIR, UPLOADS_XLSX_DIR]:
            uploaded_files.extend(uploads_subdir.glob(f"{file_id}_*"))
        
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
        
        logger.info(f"[FILE PREVIEW] Previewed {file_id}")
        return {"preview": preview}
    except Exception as e:
        logger.error(f"Error previewing file: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/files/process")
async def process_file(request: ProcessFileRequest):
    """Process an uploaded file through the ETL pipeline and save to organized folders"""
    try:
        # Search in all upload type directories
        uploaded_files = []
        file_type_found = None
        for file_type, uploads_subdir in [('csv', UPLOADS_CSV_DIR), ('json', UPLOADS_JSON_DIR), ('xlsx', UPLOADS_XLSX_DIR)]:
            found_files = list(uploads_subdir.glob(f"{request.file_id}_*"))
            if found_files:
                uploaded_files = found_files
                file_type_found = file_type
                break
        
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
        
        # Transform data - Always clean before deduping (same as CSV/JSON)
        transformed_df = df.copy()

        # Clean data: trim whitespace from string columns first so
        # values that differ only by spaces are treated as the same row.
        for col in transformed_df.columns:
            if transformed_df[col].dtype == 'object':
                transformed_df[col] = transformed_df[col].astype(str).str.strip()

        # Remove rows where all values are empty
        transformed_df = transformed_df.dropna(how='all')
        transformed_df = transformed_df[transformed_df.astype(str).ne('').any(axis=1)]

        # Remove duplicates after cleaning (matches frontend logic)
        rows_before_dedup = len(transformed_df)
        transformed_df = transformed_df.drop_duplicates()
        duplicate_count = rows_before_dedup - len(transformed_df)
        
        rows_after_transform = len(transformed_df)
        
        # Apply additional transformations if provided
        if request.transformations:
            transformed_df = Transformer.transform(transformed_df, request.transformations)
            rows_after_transform = len(transformed_df)
        
        # Generate output file
        output_file_id = str(uuid.uuid4())
        output_filename = f"{output_file_id}_processed.xlsx"
        
        # Get appropriate processed directory based on file type
        processed_type_dir = get_processed_dir_by_type(file_ext)
        output_path = processed_type_dir / output_filename
        
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
        
        logger.info(f"[FILE PROCESS] Processed {request.file_id} ({file_type_found}) -> {output_filename}")
        
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
            "rows_after": rows_after_transform,
            "file_type": file_type_found
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
        # Search in all processed type directories
        processed_files = []
        for processed_subdir in [PROCESSED_CSV_DIR, PROCESSED_JSON_DIR, PROCESSED_XLSX_DIR]:
            processed_files.extend(processed_subdir.glob(f"{file_id}_*"))
        
        if not processed_files:
            raise HTTPException(status_code=404, detail="File not found")
        
        file_path = processed_files[0]
        logger.info(f"[FILE DOWNLOAD] Downloaded {file_id}")
        return FileResponse(
            path=str(file_path),
            filename=file_path.name,
            media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    except Exception as e:
        logger.error(f"Error downloading file: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== API Gateway Observability Endpoints ====================

@app.get("/api/gateway/telemetry")
async def get_api_gateway_telemetry(
    hours: int = Query(24, ge=1, le=168),  # Default 24 hours, max 7 days
    connector_id: Optional[str] = None
):
    """
    Get aggregated API telemetry data for the API Gateway dashboard.
    Returns error rates, latency metrics, request volumes, and failure trends.
    """
    try:
        pool = get_pool()
        if pool is None:
            raise HTTPException(status_code=500, detail="Database not connected")
        
        time_threshold = datetime.utcnow() - timedelta(hours=hours)
        
        async with pool.acquire() as conn:
            # Base query conditions
            connector_filter = "AND connector_id = $2" if connector_id else ""
            params = [time_threshold]
            if connector_id:
                params.append(connector_id)
            
            # 1. Overall statistics
            overall_stats_query = f"""
                SELECT 
                    COUNT(*) as total_requests,
                    COUNT(CASE WHEN status_code >= 400 AND status_code < 500 THEN 1 END) as error_4xx,
                    COUNT(CASE WHEN status_code >= 500 THEN 1 END) as error_5xx,
                    AVG(response_time_ms) as avg_latency_ms,
                    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY response_time_ms) as p50_latency_ms,
                    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY response_time_ms) as p95_latency_ms,
                    PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY response_time_ms) as p99_latency_ms,
                    MIN(response_time_ms) as min_latency_ms,
                    MAX(response_time_ms) as max_latency_ms
                FROM api_connector_data
                WHERE timestamp >= $1
                {connector_filter}
            """
            
            overall_stats = await conn.fetchrow(overall_stats_query, *params)
            
            # 2. Per-connector statistics
            per_connector_query = f"""
                SELECT 
                    connector_id,
                    COUNT(*) as request_count,
                    COUNT(CASE WHEN status_code >= 400 AND status_code < 500 THEN 1 END) as error_4xx,
                    COUNT(CASE WHEN status_code >= 500 THEN 1 END) as error_5xx,
                    AVG(response_time_ms) as avg_latency_ms,
                    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY response_time_ms) as p95_latency_ms,
                    MAX(timestamp) as last_request_at
                FROM api_connector_data
                WHERE timestamp >= $1
                {connector_filter}
                GROUP BY connector_id
                ORDER BY request_count DESC
            """
            
            per_connector = await conn.fetch(per_connector_query, *params)
            
            # 3. Time-series data for trends (hourly buckets)
            time_series_query = f"""
                SELECT 
                    DATE_TRUNC('hour', timestamp) as hour,
                    COUNT(*) as request_count,
                    COUNT(CASE WHEN status_code >= 400 AND status_code < 500 THEN 1 END) as error_4xx,
                    COUNT(CASE WHEN status_code >= 500 THEN 1 END) as error_5xx,
                    AVG(response_time_ms) as avg_latency_ms
                FROM api_connector_data
                WHERE timestamp >= $1
                {connector_filter}
                GROUP BY DATE_TRUNC('hour', timestamp)
                ORDER BY hour ASC
            """
            
            time_series = await conn.fetch(time_series_query, *params)
            
            # 4. Status code distribution
            status_code_query = f"""
                SELECT 
                    status_code,
                    COUNT(*) as count
                FROM api_connector_data
                WHERE timestamp >= $1 AND status_code IS NOT NULL
                {connector_filter}
                GROUP BY status_code
                ORDER BY count DESC
            """
            
            status_codes = await conn.fetch(status_code_query, *params)
            
            # 5. Recent failures (last 50)
            failures_query = f"""
                SELECT 
                    connector_id,
                    timestamp,
                    status_code,
                    response_time_ms,
                    id
                FROM api_connector_data
                WHERE timestamp >= $1 AND status_code >= 400
                {connector_filter}
                ORDER BY timestamp DESC
                LIMIT 50
            """
            
            recent_failures = await conn.fetch(failures_query, *params)
            
            # 6. Pipeline run statistics
            pipeline_stats_query = f"""
                SELECT 
                    COUNT(*) as total_runs,
                    COUNT(CASE WHEN status = 'success' THEN 1 END) as successful_runs,
                    COUNT(CASE WHEN status = 'failure' THEN 1 END) as failed_runs,
                    COUNT(CASE WHEN status = 'running' THEN 1 END) as running_runs,
                    AVG(EXTRACT(EPOCH FROM (completed_at - started_at)) * 1000) as avg_run_duration_ms
                FROM pipeline_runs
                WHERE started_at >= $1
            """
            
            pipeline_params = [time_threshold]
            pipeline_stats = await conn.fetchrow(pipeline_stats_query, *pipeline_params)
            
            # Format results
            def format_row(row):
                return dict(row) if row else {}
            
            return {
                "overall": {
                    "total_requests": overall_stats["total_requests"] or 0,
                    "error_4xx": overall_stats["error_4xx"] or 0,
                    "error_5xx": overall_stats["error_5xx"] or 0,
                    "error_rate": (
                        ((overall_stats["error_4xx"] or 0) + (overall_stats["error_5xx"] or 0)) / 
                        max(overall_stats["total_requests"] or 1, 1) * 100
                    ),
                    "avg_latency_ms": float(overall_stats["avg_latency_ms"]) if overall_stats["avg_latency_ms"] else None,
                    "p50_latency_ms": float(overall_stats["p50_latency_ms"]) if overall_stats["p50_latency_ms"] else None,
                    "p95_latency_ms": float(overall_stats["p95_latency_ms"]) if overall_stats["p95_latency_ms"] else None,
                    "p99_latency_ms": float(overall_stats["p99_latency_ms"]) if overall_stats["p99_latency_ms"] else None,
                    "min_latency_ms": overall_stats["min_latency_ms"],
                    "max_latency_ms": overall_stats["max_latency_ms"],
                },
                "per_connector": [
                    {
                        "connector_id": row["connector_id"],
                        "request_count": row["request_count"],
                        "error_4xx": row["error_4xx"] or 0,
                        "error_5xx": row["error_5xx"] or 0,
                        "error_rate": (
                            ((row["error_4xx"] or 0) + (row["error_5xx"] or 0)) / 
                            max(row["request_count"], 1) * 100
                        ),
                        "avg_latency_ms": float(row["avg_latency_ms"]) if row["avg_latency_ms"] else None,
                        "p95_latency_ms": float(row["p95_latency_ms"]) if row["p95_latency_ms"] else None,
                        "last_request_at": row["last_request_at"].isoformat() if row["last_request_at"] else None,
                    }
                    for row in per_connector
                ],
                "time_series": [
                    {
                        "hour": row["hour"].isoformat() if row["hour"] else None,
                        "request_count": row["request_count"],
                        "error_4xx": row["error_4xx"] or 0,
                        "error_5xx": row["error_5xx"] or 0,
                        "avg_latency_ms": float(row["avg_latency_ms"]) if row["avg_latency_ms"] else None,
                    }
                    for row in time_series
                ],
                "status_codes": [
                    {
                        "status_code": row["status_code"],
                        "count": row["count"],
                    }
                    for row in status_codes
                ],
                "recent_failures": [
                    {
                        "connector_id": row["connector_id"],
                        "timestamp": row["timestamp"].isoformat() if row["timestamp"] else None,
                        "status_code": row["status_code"],
                        "response_time_ms": row["response_time_ms"],
                        "id": row["id"],
                    }
                    for row in recent_failures
                ],
                "pipeline_stats": {
                    "total_runs": pipeline_stats["total_runs"] or 0,
                    "successful_runs": pipeline_stats["successful_runs"] or 0,
                    "failed_runs": pipeline_stats["failed_runs"] or 0,
                    "running_runs": pipeline_stats["running_runs"] or 0,
                    "success_rate": (
                        (pipeline_stats["successful_runs"] or 0) / 
                        max(pipeline_stats["total_runs"] or 1, 1) * 100
                    ),
                    "avg_run_duration_ms": float(pipeline_stats["avg_run_duration_ms"]) if pipeline_stats["avg_run_duration_ms"] else None,
                },
                "time_range_hours": hours,
            }
    except Exception as e:
        logger.error(f"[API GATEWAY] Failed to get telemetry: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/gateway/connectors")
async def get_api_gateway_connectors():
    """
    Get list of all API connectors with basic metadata for the API Gateway dashboard.
    """
    try:
        pool = get_pool()
        if pool is None:
            raise HTTPException(status_code=500, detail="Database not connected")
        
        async with pool.acquire() as conn:
            connectors = await conn.fetch("""
                SELECT 
                    connector_id,
                    name,
                    api_url,
                    http_method,
                    status,
                    created_at,
                    updated_at
                FROM api_connectors
                ORDER BY name ASC
            """)
            
            return [
                {
                    "connector_id": row["connector_id"],
                    "name": row["name"],
                    "api_url": row["api_url"],
                    "http_method": row["http_method"],
                    "status": row["status"],
                    "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                    "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
                }
                for row in connectors
            ]
    except Exception as e:
        logger.error(f"[API GATEWAY] Failed to get connectors: {e}")
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
    import argparse
    import asyncio as _asyncio

    parser = argparse.ArgumentParser()
    args = parser.parse_args()

    if False:  # Placeholder for future command-line arguments
        pass
    else:
        uvicorn.run(
            "main:app",
            host="0.0.0.0",
            port=int(os.getenv("PORT", 8000)),
            reload=True,
            reload_dirs=["."]
        )

