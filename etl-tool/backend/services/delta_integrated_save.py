"""
Delta-Integrated Save Service

Implements robust delta logic for scheduled APIs:
- Transforms API responses to include only required fields
- Compares with existing database records
- Processes only new or updated records (delta)
- Uses UPSERT operations to prevent duplicates
- Updates pipeline counts only for delta records
"""

import logging
import json
import hashlib
import uuid
from typing import Dict, List, Any, Optional
from datetime import datetime

from services.delta_processor import process_api_data_with_delta, DeltaProcessor
from services.api_data_transformer import transform_api_response
from database import get_pool, update_pipeline_counts

logger = logging.getLogger(__name__)


async def save_to_database_with_delta(message: dict) -> Dict[str, Any]:
    """
    Save API data to database using delta logic.
    
    This function:
    1. Transforms API response to include only required fields
    2. Compares with existing records using primary keys
    3. Processes only new or updated records (delta)
    4. Uses UPSERT operations to prevent duplicates
    5. Updates pipeline counts only for delta records
    
    Args:
        message: Message dict with:
            - connector_id: API connector identifier
            - data: Raw API response data
            - raw_response: Raw response text
            - timestamp: Ingestion timestamp
            - pipeline_run_id: Pipeline run ID
            - status_code: HTTP status code
            - response_time_ms: Response time in milliseconds
    
    Returns:
        Dict with save results:
        {
            "records_saved": int,  # Total records saved (new + updated)
            "new_count": int,  # New records
            "updated_count": int,  # Updated records
            "unchanged_count": int,  # Unchanged records (not saved)
            "ids": List[int],  # Database IDs of saved records
            "error": bool,  # True if error occurred
            "error_message": str,  # Error message if error occurred
        }
    """
    try:
        connector_id = message.get("connector_id") or "unknown"
        raw_data = message.get("data")
        raw_response = message.get("raw_response", "")
        timestamp_str = message.get("timestamp")
        pipeline_run_id = message.get("pipeline_run_id")
        status_code = message.get("status_code", 200)
        response_time_ms = message.get("response_time_ms", 0)
        
        # Validate required data
        if raw_data is None:
            error_msg = f"No data provided for {connector_id}"
            logger.error(f"[DELTA] {error_msg}")
            return {
                "error": True,
                "error_type": "ValidationError",
                "error_message": error_msg,
                "records_saved": 0,
                "new_count": 0,
                "updated_count": 0,
                "unchanged_count": 0,
                "ids": [],
            }
        
        # Parse timestamp
        if timestamp_str:
            try:
                ingestion_timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            except:
                ingestion_timestamp = datetime.utcnow()
        else:
            ingestion_timestamp = datetime.utcnow()
        
        # Step 1: Process API data with delta logic
        try:
            delta_result = await process_api_data_with_delta(
                connector_id=connector_id,
                raw_api_response=raw_data,
                ingestion_timestamp=ingestion_timestamp,
                pipeline_run_id=pipeline_run_id
            )
        except Exception as delta_error:
            error_msg = f"Delta processing failed for {connector_id}: {str(delta_error)}"
            logger.error(f"[DELTA] {error_msg}", exc_info=True)
            # Return error result instead of raising to prevent continuous error spam
            return {
                "error": True,
                "error_type": type(delta_error).__name__,
                "error_message": error_msg,
                "error_details": str(delta_error),
                "records_saved": 0,
                "new_count": 0,
                "updated_count": 0,
                "unchanged_count": 0,
                "ids": [],
            }
        
        new_count = delta_result.get("new_count", 0)
        updated_count = delta_result.get("updated_count", 0)
        unchanged_count = delta_result.get("unchanged_count", 0)
        records_to_save = delta_result.get("records", [])
        
        total_processed = new_count + updated_count
        
        if not records_to_save:
            logger.info(
                f"[DELTA] {connector_id}: No delta records to save "
                f"(NEW={new_count}, UPDATED={updated_count}, UNCHANGED={unchanged_count})"
            )
            return {
                "records_saved": 0,
                "new_count": new_count,
                "updated_count": updated_count,
                "unchanged_count": unchanged_count,
                "ids": [],
            }
        
        # Step 2: Save delta records using UPSERT
        pool = get_pool()
        saved_ids = []
        saved_count = 0
        
        async with pool.acquire() as conn:
            # Generate source_id and session_id for this batch
            source_id = hashlib.md5(f"{connector_id}_{ingestion_timestamp}".encode()).hexdigest()[:16]
            session_id = str(uuid.uuid4())
            
            # Determine exchange based on connector_id
            exchange = "scheduled_api"
            if connector_id.startswith("binance"):
                exchange = "Binance"
            elif connector_id.startswith("coingecko"):
                exchange = "CoinGecko"
            elif connector_id.startswith("cryptocompare"):
                exchange = "CryptoCompare"
            
            # Save each delta record using UPSERT
            for record in records_to_save:
                try:
                    # Extract delta metadata
                    delta_metadata = record.get("_delta_metadata", {})
                    primary_key = delta_metadata.get("primary_key")
                    delta_type = delta_metadata.get("delta_type", "NEW")
                    checksum = delta_metadata.get("checksum")
                    
                    if not primary_key:
                        logger.warning(f"[DELTA] Skipping record without primary_key: {record}")
                        continue
                    
                    # Extract fields for database
                    instrument = record.get("symbol") or record.get("name") or record.get("coin_name") or "-"
                    price = record.get("price") or record.get("current_price") or record.get("price_numeric") or 0.0
                    
                    # Clean record data (remove internal metadata)
                    clean_record = {k: v for k, v in record.items() if not k.startswith("_")}
                    
                    # Add checksum to data for future comparison
                    clean_record["checksum"] = checksum
                    
                    # UPSERT operation
                    # Use unique index on (connector_id, primary_key) for conflict resolution
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
                        json.dumps(raw_data) if raw_data else None,
                        status_code,
                        response_time_ms,
                        source_id,
                        session_id,
                        primary_key,
                        delta_type,
                        pipeline_run_id
                    )
                    
                    if row_id:
                        saved_ids.append(row_id)
                        saved_count += 1
                
                except Exception as record_error:
                    logger.error(
                        f"[DELTA] Failed to save record for {connector_id}: {record_error}",
                        exc_info=True
                    )
                    continue
            
            # Step 3: Update pipeline counts ONLY for delta records
            # This ensures counts only increase, never reset
            if saved_count > 0:
                try:
                    # Update pipeline_steps with delta counts
                    # Increment extract_count by total_processed (all records from API)
                    # Increment load_count by saved_count (only delta records saved)
                    await conn.execute("""
                        INSERT INTO pipeline_steps (
                            pipeline_name, extract_count, transform_count, load_count, status, last_run_at
                        )
                        VALUES ($1, $2, $3, $4, 'COMPLETED', $5)
                        ON CONFLICT (pipeline_name)
                        DO UPDATE SET
                            extract_count = pipeline_steps.extract_count + $2,
                            transform_count = pipeline_steps.transform_count + $3,
                            load_count = pipeline_steps.load_count + $4,
                            status = 'COMPLETED',
                            last_run_at = $5
                    """,
                        connector_id,
                        len(records_to_save) + unchanged_count,  # Total records from API
                        len(records_to_save),  # Transformed records (delta)
                        saved_count,  # Loaded records (saved to DB)
                        ingestion_timestamp
                    )
                    
                    logger.info(
                        f"[DELTA] ✅ Updated pipeline counts for {connector_id}: "
                        f"EXTRACT={len(records_to_save) + unchanged_count}, "
                        f"TRANSFORM={len(records_to_save)}, LOAD={saved_count}"
                    )
                except Exception as count_error:
                    logger.error(
                        f"[DELTA] Failed to update pipeline counts for {connector_id}: {count_error}",
                        exc_info=True
                    )
        
        logger.info(
            f"[DELTA] ✅ {connector_id}: Saved {saved_count} delta records "
            f"(NEW={new_count}, UPDATED={updated_count}, UNCHANGED={unchanged_count})"
        )
        
        return {
            "records_saved": saved_count,
            "new_count": new_count,
            "updated_count": updated_count,
            "unchanged_count": unchanged_count,
            "ids": saved_ids,
            "source_id": source_id,
            "session_id": session_id,
        }
    
    except Exception as e:
        error_type = type(e).__name__
        error_message = str(e)
        logger.error(
            f"[DELTA] ❌ Error saving with delta logic: {error_message}",
            exc_info=True
        )
        
        return {
            "error": True,
            "error_type": error_type,
            "error_message": error_message,
            "error_details": str(e),
            "records_saved": 0,
            "new_count": 0,
            "updated_count": 0,
            "unchanged_count": 0,
            "ids": [],
        }
