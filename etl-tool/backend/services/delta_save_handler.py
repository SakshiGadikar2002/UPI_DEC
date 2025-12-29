"""
Delta Save Handler

Handles database UPSERT operations with delta logic.
Ensures only new/updated records are saved using proper UPSERT.
"""

import logging
import json
import hashlib
import uuid
from typing import Dict, List, Any, Optional
from datetime import datetime

from database import get_pool

logger = logging.getLogger(__name__)


async def save_delta_records(
    connector_id: str,
    delta_records: List[Dict[str, Any]],
    ingestion_timestamp: datetime,
    pipeline_run_id: Optional[int] = None,
    exchange: str = "scheduled_api",
    status_code: int = 200,
    response_time_ms: int = 0
) -> Dict[str, Any]:
    """
    Save delta records to database using UPSERT.
    
    Args:
        connector_id: API connector identifier
        delta_records: List of records to save (already filtered by delta logic)
        ingestion_timestamp: Timestamp when data was ingested
        pipeline_run_id: Optional pipeline run ID
        exchange: Exchange name
        status_code: HTTP status code
        response_time_ms: Response time in milliseconds
    
    Returns:
        Dict with save results:
        {
            "saved_count": int,
            "new_count": int,
            "updated_count": int,
            "inserted_ids": List[int]
        }
    """
    if not delta_records:
        return {
            "saved_count": 0,
            "new_count": 0,
            "updated_count": 0,
            "inserted_ids": []
        }
    
    pool = get_pool()
    saved_count = 0
    new_count = 0
    updated_count = 0
    inserted_ids = []
    
    source_id = hashlib.md5(f"{connector_id}_{ingestion_timestamp}".encode()).hexdigest()[:16]
    session_id = str(uuid.uuid4())
    
    async with pool.acquire() as conn:
        async with conn.transaction():
            for record in delta_records:
                try:
                    # Extract delta metadata
                    delta_metadata = record.get("_delta_metadata", {})
                    primary_key = delta_metadata.get("primary_key")
                    delta_type = delta_metadata.get("delta_type", "NEW")
                    checksum = delta_metadata.get("checksum")
                    
                    # Remove metadata from record before storing
                    clean_record = {k: v for k, v in record.items() if not k.startswith("_")}
                    
                    # Extract fields for database
                    instrument = clean_record.get("symbol") or clean_record.get("name") or clean_record.get("coin_symbol") or "-"
                    price = clean_record.get("price") or clean_record.get("current_price") or clean_record.get("price_usd") or clean_record.get("best_bid_price") or 0.0
                    
                    if price is None:
                        price = 0.0
                    
                    # Store primary_key and checksum in data JSONB for querying
                    clean_record["primary_key"] = primary_key
                    clean_record["checksum"] = checksum
                    clean_record["delta_type"] = delta_type
                    clean_record["pipeline_run_id"] = pipeline_run_id
                    clean_record["processed_at"] = ingestion_timestamp.isoformat()
                    
                    # UPSERT operation
                    # Use primary_key column for conflict resolution (unique index on connector_id + primary_key)
                    row_id = await conn.fetchval("""
                        INSERT INTO api_connector_data (
                            connector_id,
                            timestamp,
                            exchange,
                            instrument,
                            price,
                            data,
                            message_type,
                            raw_response,
                            status_code,
                            response_time_ms,
                            source_id,
                            session_id,
                            primary_key,
                            delta_type,
                            pipeline_run_id
                        )
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
                        ON CONFLICT (connector_id, primary_key)
                        DO UPDATE SET
                            timestamp = EXCLUDED.timestamp,
                            exchange = EXCLUDED.exchange,
                            instrument = EXCLUDED.instrument,
                            price = EXCLUDED.price,
                            data = EXCLUDED.data,
                            raw_response = EXCLUDED.raw_response,
                            status_code = EXCLUDED.status_code,
                            response_time_ms = EXCLUDED.response_time_ms,
                            source_id = EXCLUDED.source_id,
                            session_id = EXCLUDED.session_id,
                            delta_type = EXCLUDED.delta_type,
                            pipeline_run_id = EXCLUDED.pipeline_run_id
                        RETURNING id
                    """,
                        connector_id,
                        ingestion_timestamp,
                        exchange,
                        instrument,
                        float(price) if price else 0.0,
                        json.dumps(clean_record),
                        "scheduled_api_call",
                        json.dumps(clean_record),  # Use clean record as raw_response
                        status_code,
                        response_time_ms,
                        source_id,
                        session_id,
                        primary_key,
                        delta_type,
                        pipeline_run_id
                    )
                    
                    if row_id:
                        inserted_ids.append(row_id)
                        saved_count += 1
                        
                        if delta_type == "NEW":
                            new_count += 1
                        elif delta_type == "UPDATED":
                            updated_count += 1
                
                except Exception as e:
                    logger.error(f"[DELTA_SAVE] Failed to save record for {connector_id}: {e}", exc_info=True)
                    continue
    
    logger.info(
        f"[DELTA_SAVE] ✅ {connector_id}: Saved {saved_count} records "
        f"(NEW={new_count}, UPDATED={updated_count})"
    )
    
    return {
        "saved_count": saved_count,
        "new_count": new_count,
        "updated_count": updated_count,
        "inserted_ids": inserted_ids
    }


async def update_pipeline_counts_delta(
    connector_id: str,
    new_count: int,
    updated_count: int
) -> None:
    """
    Update pipeline counts with delta records only.
    Increments counts, never resets.
    
    Args:
        connector_id: API connector identifier
        new_count: Number of new records
        updated_count: Number of updated records
    """
    pool = get_pool()
    if pool is None:
        logger.warning(f"[PIPELINE] Pool not available, cannot update counts for {connector_id}")
        return
    
    total_delta = new_count + updated_count
    
    if total_delta == 0:
        return  # No delta records, no count update needed
    
    try:
        async with pool.acquire() as conn:
            # Get current counts
            current = await conn.fetchrow("""
                SELECT extract_count, transform_count, load_count
                FROM pipeline_steps
                WHERE pipeline_name = $1
            """, connector_id)
            
            current_extract = current['extract_count'] if current else 0
            current_transform = current['transform_count'] if current else 0
            current_load = current['load_count'] if current else 0
            
            # Increment counts (never reset)
            new_extract = current_extract + total_delta
            new_transform = current_transform + total_delta
            new_load = current_load + total_delta
            
            # Update pipeline_steps
            await conn.execute("""
                INSERT INTO pipeline_steps (pipeline_name, extract_count, transform_count, load_count, status, last_run_at)
                VALUES ($1, $2, $3, $4, 'COMPLETED', NOW())
                ON CONFLICT (pipeline_name) 
                DO UPDATE SET 
                    extract_count = $2,
                    transform_count = $3,
                    load_count = $4,
                    status = 'COMPLETED',
                    last_run_at = NOW()
            """, connector_id, new_extract, new_transform, new_load)
            
            logger.info(
                f"[PIPELINE] ✅ Updated delta counts for {connector_id}: "
                f"+{total_delta} (NEW={new_count}, UPDATED={updated_count})"
            )
    
    except Exception as e:
        logger.error(f"[PIPELINE] ❌ Failed to update delta counts for {connector_id}: {e}", exc_info=True)

