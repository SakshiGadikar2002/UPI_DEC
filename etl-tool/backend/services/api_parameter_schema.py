"""
API Parameter Schema Configuration

Defines locked, required parameters for all 8 scheduled APIs.
Only these fields will be stored in the database to ensure:
- Data consistency
- Correct delta logic
- Accurate pipeline visualization
- Performance optimization
"""

from typing import Dict, List, Any, Optional
from datetime import datetime


# Schema definition for each API
API_PARAMETER_SCHEMAS: Dict[str, Dict[str, Any]] = {
    "binance_orderbook": {
        "api_name": "Binance - Order Book (BTC/USDT)",
        "response_type": "dict",
        "primary_identifier": "symbol",  # For delta comparison
        "timestamp_field": None,  # Use ingestion timestamp
        "required_fields": {
            "symbol": str,  # Trading pair (e.g., "BTCUSDT")
            "bids": List[List[float]],  # Best bid prices and quantities
            "asks": List[List[float]],  # Best ask prices and quantities
        },
        "extract_rules": {
            "best_bid_price": lambda data: float(data["bids"][0][0]) if data.get("bids") and len(data["bids"]) > 0 else None,
            "best_bid_quantity": lambda data: float(data["bids"][0][1]) if data.get("bids") and len(data["bids"]) > 0 else None,
            "best_ask_price": lambda data: float(data["asks"][0][0]) if data.get("asks") and len(data["asks"]) > 0 else None,
            "best_ask_quantity": lambda data: float(data["asks"][0][1]) if data.get("asks") and len(data["asks"]) > 0 else None,
        },
        "business_fields": [
            "symbol",
            "best_bid_price",
            "best_bid_quantity",
            "best_ask_price",
            "best_ask_quantity",
        ],
        "delta_comparison_fields": ["best_bid_price", "best_ask_price"],  # Fields to compare for delta
        "exclude_fields": ["lastUpdateId"],  # Unnecessary metadata
    },
    
    "binance_prices": {
        "api_name": "Binance - Current Prices",
        "response_type": "list",
        "primary_identifier": "symbol",  # Unique per item
        "timestamp_field": None,  # Use ingestion timestamp
        "required_fields": {
            "symbol": str,  # Trading pair symbol
            "price": str,  # Current price (as string from API)
        },
        "extract_rules": {
            "price_numeric": lambda item: float(item.get("price", 0)) if item.get("price") else 0.0,
        },
        "business_fields": [
            "symbol",
            "price",
            "price_numeric",
        ],
        "delta_comparison_fields": ["price"],  # Compare price for changes
        "exclude_fields": [],  # All fields are needed
    },
    
    "binance_24hr": {
        "api_name": "Binance - 24hr Ticker",
        "response_type": "list",
        "primary_identifier": "symbol",  # Unique per item
        "timestamp_field": None,  # Use ingestion timestamp
        "required_fields": {
            "symbol": str,  # Trading pair symbol
            "lastPrice": str,  # Last price
            "priceChangePercent": str,  # 24h price change percentage
            "quoteAssetVolume": str,  # 24h volume in quote asset
            "highPrice": str,  # 24h high price
            "lowPrice": str,  # 24h low price
        },
        "extract_rules": {
            "last_price_numeric": lambda item: float(item.get("lastPrice", 0)) if item.get("lastPrice") else 0.0,
            "price_change_numeric": lambda item: float(item.get("priceChangePercent", 0)) if item.get("priceChangePercent") else 0.0,
            "volume_numeric": lambda item: float(item.get("quoteAssetVolume", 0)) if item.get("quoteAssetVolume") else 0.0,
            "high_price_numeric": lambda item: float(item.get("highPrice", 0)) if item.get("highPrice") else 0.0,
            "low_price_numeric": lambda item: float(item.get("lowPrice", 0)) if item.get("lowPrice") else 0.0,
        },
        "business_fields": [
            "symbol",
            "lastPrice",
            "last_price_numeric",
            "priceChangePercent",
            "price_change_numeric",
            "quoteAssetVolume",
            "volume_numeric",
            "highPrice",
            "high_price_numeric",
            "lowPrice",
            "low_price_numeric",
        ],
        "delta_comparison_fields": ["lastPrice", "priceChangePercent"],  # Compare for changes
        "exclude_fields": [
            "openPrice", "prevClosePrice", "weightedAvgPrice",  # Not needed for business logic
            "count", "firstId", "lastId",  # Trade count metadata
        ],
    },
    
    "coingecko_global": {
        "api_name": "CoinGecko - Global Market",
        "response_type": "dict",
        "primary_identifier": "global_stats",  # Single record identifier
        "timestamp_field": None,  # Use ingestion timestamp
        "required_fields": {
            "data": {
                "total_market_cap": {"usd": float},  # Total market cap in USD
                "total_volume": {"usd": float},  # Total 24h volume in USD
                "market_cap_percentage": dict,  # Market cap percentage by coin
                "active_cryptocurrencies": int,  # Number of active cryptocurrencies
                "markets": int,  # Number of markets
            }
        },
        "extract_rules": {
            "total_market_cap_usd": lambda data: data.get("data", {}).get("total_market_cap", {}).get("usd", 0.0),
            "total_volume_usd": lambda data: data.get("data", {}).get("total_volume", {}).get("usd", 0.0),
            "active_cryptocurrencies": lambda data: data.get("data", {}).get("active_cryptocurrencies", 0),
            "markets": lambda data: data.get("data", {}).get("markets", 0),
            "btc_dominance": lambda data: data.get("data", {}).get("market_cap_percentage", {}).get("btc", 0.0),
            "eth_dominance": lambda data: data.get("data", {}).get("market_cap_percentage", {}).get("eth", 0.0),
        },
        "business_fields": [
            "total_market_cap_usd",
            "total_volume_usd",
            "active_cryptocurrencies",
            "markets",
            "btc_dominance",
            "eth_dominance",
        ],
        "delta_comparison_fields": ["total_market_cap_usd", "total_volume_usd"],  # Compare for changes
        "exclude_fields": ["updated_at"],  # Use ingestion timestamp instead
    },
    
    "coingecko_top": {
        "api_name": "CoinGecko - Top Cryptocurrencies",
        "response_type": "list",
        "primary_identifier": "id",  # CoinGecko coin ID (unique)
        "timestamp_field": None,  # Use ingestion timestamp
        "required_fields": {
            "id": str,  # CoinGecko coin ID (e.g., "bitcoin")
            "symbol": str,  # Coin symbol (e.g., "btc")
            "name": str,  # Coin name (e.g., "Bitcoin")
            "current_price": float,  # Current price in USD
            "market_cap": float,  # Market capitalization
            "market_cap_rank": int,  # Market cap ranking
            "total_volume": float,  # 24h trading volume
            "price_change_percentage_24h": float,  # 24h price change percentage
            "high_24h": float,  # 24h high price
            "low_24h": float,  # 24h low price
        },
        "extract_rules": {
            # Fields are already in correct format, just validate
            "price": lambda item: float(item.get("current_price", 0)) if item.get("current_price") is not None else 0.0,
            "market_cap": lambda item: float(item.get("market_cap", 0)) if item.get("market_cap") is not None else 0.0,
            "volume": lambda item: float(item.get("total_volume", 0)) if item.get("total_volume") is not None else 0.0,
            "price_change_24h": lambda item: float(item.get("price_change_percentage_24h", 0)) if item.get("price_change_percentage_24h") is not None else 0.0,
        },
        "business_fields": [
            "id",
            "symbol",
            "name",
            "current_price",
            "price",
            "market_cap",
            "market_cap_rank",
            "total_volume",
            "volume",
            "price_change_percentage_24h",
            "price_change_24h",
            "high_24h",
            "low_24h",
        ],
        "delta_comparison_fields": ["current_price", "market_cap", "price_change_percentage_24h"],  # Compare for changes
        "exclude_fields": [
            "image", "last_updated",  # Not needed for business logic
            "fully_diluted_valuation", "total_value_locked",  # Advanced metrics not needed
            "ath", "ath_change_percentage", "ath_date",  # All-time high data not needed
            "atl", "atl_change_percentage", "atl_date",  # All-time low data not needed
            "roi", "sparkline_in_7d",  # Not needed
        ],
    },
    
    "coingecko_trending": {
        "api_name": "CoinGecko - Trending Coins",
        "response_type": "dict",
        "primary_identifier": "item.id",  # Nested: coins[].item.id
        "timestamp_field": None,  # Use ingestion timestamp
        "required_fields": {
            "coins": List[Dict[str, Any]],  # List of trending coins
            # Each coin has: item { id, name, symbol, market_cap_rank }
        },
        "extract_rules": {
            "extract_coins": lambda data: [
                {
                    "id": coin.get("item", {}).get("id", ""),
                    "name": coin.get("item", {}).get("name", ""),
                    "symbol": coin.get("item", {}).get("symbol", "").upper(),
                    "market_cap_rank": coin.get("item", {}).get("market_cap_rank", 0),
                    "score": coin.get("item", {}).get("score", 0),
                }
                for coin in data.get("coins", [])
            ],
        },
        "business_fields": [
            "id",
            "name",
            "symbol",
            "market_cap_rank",
            "score",
        ],
        "delta_comparison_fields": ["id", "market_cap_rank"],  # Compare trending list
        "exclude_fields": [
            "item.slug", "item.small", "item.thumb", "item.large",  # Image URLs not needed
            "item.data.price", "item.data.price_btc",  # Price data not reliable in trending
        ],
    },
    
    "cryptocompare_multi": {
        "api_name": "CryptoCompare - Multi Price",
        "response_type": "dict",
        "primary_identifier": "symbol",  # Dict key (e.g., "BTC", "ETH")
        "timestamp_field": None,  # Use ingestion timestamp
        "required_fields": {
            # Structure: { "BTC": { "USD": 45000 }, "ETH": { "USD": 3000 } }
            "symbol": str,  # Dict key
            "USD": float,  # Price in USD
        },
        "extract_rules": {
            "extract_prices": lambda data: [
                {
                    "symbol": symbol,
                    "price_usd": float(prices.get("USD", 0)) if prices.get("USD") else 0.0,
                }
                for symbol, prices in data.items()
                if isinstance(prices, dict) and "USD" in prices
            ],
        },
        "business_fields": [
            "symbol",
            "price_usd",
        ],
        "delta_comparison_fields": ["price_usd"],  # Compare price for changes
        "exclude_fields": [],  # All fields are needed
    },
    
    "cryptocompare_top": {
        "api_name": "CryptoCompare - Top Coins",
        "response_type": "dict",
        "primary_identifier": "CoinInfo.Name",  # Nested: Data[].CoinInfo.Name
        "timestamp_field": None,  # Use ingestion timestamp
        "required_fields": {
            "Data": List[Dict[str, Any]],  # List of top coins
            # Each item has: CoinInfo { Name, FullName, Symbol }, DISPLAY.USD { PRICE, MKTCAP, VOLUME24H }
        },
        "extract_rules": {
            "extract_coins": lambda data: [
                {
                    "name": item.get("CoinInfo", {}).get("Name", ""),
                    "full_name": item.get("CoinInfo", {}).get("FullName", ""),
                    "symbol": item.get("CoinInfo", {}).get("Symbol", ""),
                    "price_usd": float(
                        item.get("DISPLAY", {}).get("USD", {}).get("PRICE", "0")
                        .replace("$", "").replace(",", "")
                    ) if item.get("DISPLAY", {}).get("USD", {}).get("PRICE") else 0.0,
                    "market_cap": item.get("DISPLAY", {}).get("USD", {}).get("MKTCAP", ""),
                    "volume_24h": item.get("DISPLAY", {}).get("USD", {}).get("VOLUME24H", ""),
                }
                for item in data.get("Data", [])
                if item.get("CoinInfo")
            ],
        },
        "business_fields": [
            "name",
            "full_name",
            "symbol",
            "price_usd",
            "market_cap",
            "volume_24h",
        ],
        "delta_comparison_fields": ["name", "price_usd"],  # Compare for changes
        "exclude_fields": [
            "RAW",  # Raw numeric data (use DISPLAY instead)
            "CoinInfo.Url", "CoinInfo.ImageUrl",  # URLs not needed
        ],
    },
}


def get_api_schema(connector_id: str) -> Optional[Dict[str, Any]]:
    """Get parameter schema for a specific API connector."""
    return API_PARAMETER_SCHEMAS.get(connector_id)


def get_primary_identifier(connector_id: str) -> Optional[str]:
    """Get primary identifier field name for an API."""
    schema = get_api_schema(connector_id)
    return schema.get("primary_identifier") if schema else None


def get_delta_comparison_fields(connector_id: str) -> List[str]:
    """Get fields used for delta comparison."""
    schema = get_api_schema(connector_id)
    return schema.get("delta_comparison_fields", []) if schema else []


def get_business_fields(connector_id: str) -> List[str]:
    """Get required business fields for an API."""
    schema = get_api_schema(connector_id)
    return schema.get("business_fields", []) if schema else []


def get_excluded_fields(connector_id: str) -> List[str]:
    """Get fields to exclude from storage."""
    schema = get_api_schema(connector_id)
    return schema.get("exclude_fields", []) if schema else None


def validate_schema_consistency():
    """
    Validate that all schemas have required keys and consistent structure.
    Raises ValueError if any schema is invalid.
    """
    required_keys = [
        "api_name",
        "response_type",
        "primary_identifier",
        "required_fields",
        "business_fields",
        "delta_comparison_fields",
    ]
    
    for connector_id, schema in API_PARAMETER_SCHEMAS.items():
        for key in required_keys:
            if key not in schema:
                raise ValueError(
                    f"Schema for {connector_id} is missing required key: {key}"
                )
        
        # Validate primary_identifier exists in business_fields or extract_rules
        primary_id = schema.get("primary_identifier")
        if primary_id and primary_id not in schema.get("business_fields", []):
            # Check if it's in extract_rules
            extract_rules = schema.get("extract_rules", {})
            if primary_id not in extract_rules:
                # Check if it's a nested field (e.g., "item.id")
                if "." in primary_id:
                    # Nested field, assume it's extracted correctly
                    pass
                else:
                    raise ValueError(
                        f"Schema for {connector_id}: primary_identifier '{primary_id}' "
                        f"not found in business_fields or extract_rules"
                    )


# Validate schemas on import
try:
    validate_schema_consistency()
except ValueError as e:
    import logging
    logger = logging.getLogger(__name__)
    logger.error(f"API Parameter Schema validation failed: {e}")
    raise

