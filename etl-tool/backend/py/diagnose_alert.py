#!/usr/bin/env python3
"""
Diagnostic script to check alert system status
"""
import asyncio
import asyncpg
import os
import sys
from dotenv import load_dotenv

load_dotenv()

async def main():
    # Connect to database
    pool = await asyncpg.create_pool(
        host=os.getenv('POSTGRES_HOST', 'localhost'),
        port=int(os.getenv('POSTGRES_PORT', 5432)),
        user=os.getenv('POSTGRES_USER', 'postgres'),
        password=os.getenv('POSTGRES_PASSWORD'),
        database=os.getenv('POSTGRES_DB', 'etl_tool')
    )
    
    async with pool.acquire() as conn:
        print("=" * 80)
        print("ALERT SYSTEM DIAGNOSTICS")
        print("=" * 80)
        
        # Check alert rules
        print("\n[1] Alert Rules in Database:")
        print("-" * 80)
        rules = await conn.fetch("SELECT id, name, alert_type, symbol, price_threshold, price_comparison, enabled FROM alert_rules")
        if rules:
            for rule in rules:
                print(f"  ID {rule['id']}: {rule['name']}")
                print(f"    - Type: {rule['alert_type']}")
                print(f"    - Symbol: {rule['symbol']}")
                print(f"    - Threshold: {rule['price_threshold']}")
                print(f"    - Comparison: {rule['price_comparison']}")
                print(f"    - Enabled: {rule['enabled']}")
        else:
            print("  ❌ No alert rules found!")
        
        # Check price history
        print("\n[2] Price History Data:")
        print("-" * 80)
        prices = await conn.fetch("SELECT id, symbol, price, timestamp FROM price_history ORDER BY timestamp DESC LIMIT 10")
        if prices:
            for price in prices:
                print(f"  {price['symbol']}: ${price['price']} at {price['timestamp']}")
        else:
            print("  ❌ No price history data found!")
        
        # Check if BTC price would trigger rule 2 (if it exists)
        print("\n[3] Alert Trigger Check (Rule 2):")
        print("-" * 80)
        rule = await conn.fetchrow("SELECT * FROM alert_rules WHERE id = 2")
        if rule:
            price = await conn.fetchval(
                "SELECT price FROM price_history WHERE symbol = $1 ORDER BY timestamp DESC LIMIT 1",
                rule['symbol']
            )
            if price:
                price_float = float(price)
                threshold = float(rule['price_threshold'])
                print(f"  Rule: {rule['name']}")
                print(f"  Symbol: {rule['symbol']}")
                print(f"  Current Price: ${price_float}")
                print(f"  Threshold: ${threshold}")
                print(f"  Comparison: {rule['price_comparison']}")
                
                should_trigger = False
                if rule['price_comparison'] == 'greater' and price_float > threshold:
                    should_trigger = True
                    print(f"  Result: ✅ SHOULD TRIGGER ({price_float} > {threshold})")
                elif rule['price_comparison'] == 'less' and price_float < threshold:
                    should_trigger = True
                    print(f"  Result: ✅ SHOULD TRIGGER ({price_float} < {threshold})")
                else:
                    print(f"  Result: ❌ Would NOT trigger ({price_float} vs {threshold})")
            else:
                print(f"  ❌ No price found for {rule['symbol']}")
        else:
            print("  ❌ Rule 2 not found!")
        
        # Check alert logs
        print("\n[4] Alert Logs:")
        print("-" * 80)
        logs = await conn.fetch("SELECT id, rule_id, alert_type, title, severity, status, created_at FROM alert_logs ORDER BY created_at DESC LIMIT 5")
        if logs:
            for log in logs:
                print(f"  Alert {log['id']}: Rule {log['rule_id']} - {log['title']}")
                print(f"    - Type: {log['alert_type']}, Severity: {log['severity']}, Status: {log['status']}")
        else:
            print("  ℹ️  No alert logs yet (normal if alerts haven't been triggered)")
        
        # Check database connection
        print("\n[5] Database Connection:")
        print("-" * 80)
        try:
            result = await conn.fetchval("SELECT 1")
            print(f"  ✅ Database connection successful")
        except Exception as e:
            print(f"  ❌ Database connection failed: {e}")
        
        print("\n" + "=" * 80)
    
    await pool.close()

if __name__ == "__main__":
    asyncio.run(main())
