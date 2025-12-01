"""
Test script to verify data extraction logic
Run: python test_data_extraction.py
"""

# Test data structures
test_cases = [
    # Binance stream format
    {
        "name": "Binance Stream Format",
        "data": {
            "stream": "btcusdt@trade",
            "data": {
                "e": "trade",
                "s": "BTCUSDT",
                "p": "50000.50",
                "q": "0.1",
                "t": 1234567890
            }
        },
        "expected_instrument": "BTC-USDT",
        "expected_price": 50000.50
    },
    # Binance direct format
    {
        "name": "Binance Direct Format",
        "data": {
            "e": "trade",
            "s": "BTCUSDT",
            "p": "50000.50",
            "q": "0.1"
        },
        "expected_instrument": "BTC-USDT",
        "expected_price": 50000.50
    },
    # OKX format
    {
        "name": "OKX Format",
        "data": {
            "arg": {
                "channel": "trades",
                "instId": "BTC-USDT"
            },
            "data": [
                {
                    "instId": "BTC-USDT",
                    "px": "50000.50",
                    "sz": "0.1",
                    "side": "buy"
                }
            ]
        },
        "expected_instrument": "BTC-USDT",
        "expected_price": 50000.50
    },
    # Binance 24hrTicker
    {
        "name": "Binance 24hrTicker",
        "data": {
            "e": "24hrTicker",
            "s": "ETHUSDT",
            "c": "3000.25"
        },
        "expected_instrument": "ETH-USDT",
        "expected_price": 3000.25
    }
]

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
            if len(symbol) == 6:
                return f"{symbol[:3]}-{symbol[3:]}"
            return symbol
        # Binance direct format
        if "s" in data_obj:
            symbol = data_obj["s"]
            if len(symbol) == 6:
                return f"{symbol[:3]}-{symbol[3:]}"
            return symbol
        # Check nested data
        if "data" in data_obj:
            if isinstance(data_obj["data"], list) and len(data_obj["data"]) > 0:
                trade = data_obj["data"][0]
                if isinstance(trade, dict) and "instId" in trade:
                    return trade["instId"]
            elif isinstance(data_obj["data"], dict):
                return extract_instrument(data_obj["data"])
    return None

def extract_price(data_obj):
    """Extract price from various data formats"""
    if not data_obj:
        return None
    if isinstance(data_obj, dict):
        for price_field in ["px", "p", "last", "c", "price"]:
            if price_field in data_obj and data_obj[price_field]:
                try:
                    return float(data_obj[price_field])
                except (ValueError, TypeError):
                    continue
        if "data" in data_obj:
            if isinstance(data_obj["data"], list) and len(data_obj["data"]) > 0:
                return extract_price(data_obj["data"][0])
            elif isinstance(data_obj["data"], dict):
                return extract_price(data_obj["data"])
    elif isinstance(data_obj, list) and len(data_obj) > 0:
        return extract_price(data_obj[0])
    return None

# Run tests
print("Testing data extraction logic...\n")
all_passed = True

for test in test_cases:
    instrument = extract_instrument(test["data"])
    price = extract_price(test["data"])
    
    instrument_ok = instrument == test["expected_instrument"]
    price_ok = abs(price - test["expected_price"]) < 0.01 if price and test["expected_price"] else price == test["expected_price"]
    
    status = "✅ PASS" if (instrument_ok and price_ok) else "❌ FAIL"
    if not (instrument_ok and price_ok):
        all_passed = False
    
    print(f"{status} - {test['name']}")
    print(f"   Instrument: {instrument} (expected: {test['expected_instrument']}) {'✅' if instrument_ok else '❌'}")
    print(f"   Price: {price} (expected: {test['expected_price']}) {'✅' if price_ok else '❌'}")
    print()

if all_passed:
    print("🎉 All tests passed!")
else:
    print("⚠️ Some tests failed. Check the extraction logic.")

