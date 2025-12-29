"""
Delta Processing Service for Scheduled APIs

Implements robust delta logic to process only new or updated records.
Ensures no duplicates, accurate pipeline counts, and proper UPSERT operations.
"""

import logging
import hashlib
import json
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from enum import Enum

from services.api_parameter_schema import (
    get_api_schema,
    get_primary_identifier,
    get_delta_comparison_fields,
)
from services.api_data_transformer import transform_api_response, APIDataTransformer
from database import get_pool

logger = logging.getLogger(__name__)


class DeltaType(Enum):
    """Delta record type"""
    NEW = "NEW"
    UPDATED = "UPDATED"
    UNCHANGED = "UNCHANGED"


class DeltaProcessor:
    """
    Processes API data using delta logic.
    Compares incoming records with existing database records and processes only deltas.
    """
    
    def __init__(self, connector_id: str):
        """
        Initialize delta processor for a connector.
        
        Args:
            connector_id: API connector identifier
        """
        self.connector_id = connector_id
        self.schema = get_api_schema(connector_id)
        if not self.schema:
            logger.warning(f"[DELTA] No schema found for {connector_id}, delta logic may not work correctly")
        
        self.primary_identifier = get_primary_identifier(connector_id) if self.schema else None
        self.delta_fields = get_delta_comparison_fields(connector_id) if self.schema else []
    
    def build_primary_key(self, record: Dict[str, Any]) -> Optional[str]:
        """
        Build primary key from record using primary identifier.
        
        Args:
            record: Transformed record
        
        Returns:
            Primary key string or None
        """
        if not self.primary_identifier:
            return None
        
        # Handle nested fields (e.g., "item.id")
        if "." in self.primary_identifier:
            key_field = self.primary_identifier.replace(".", "_")
        else:
            key_field = self.primary_identifier
        
        primary_value = record.get(key_field)
        if primary_value is None:
            # Try original field name
            primary_value = record.get(self.primary_identifier)
        
        if primary_value is None:
            logger.warning(f"[DELTA] Primary identifier '{self.primary_identifier}' not found in record")
            return None
        
        # Build composite key: connector_id + primary_value
        return f"{self.connector_id}:{primary_value}"
    
    def build_checksum(self, record: Dict[str, Any]) -> str:
        """
        Build checksum/hash from delta comparison fields.
        
        Args:
            record: Transformed record
        
        Returns:
            MD5 checksum string
        """
        if not self.delta_fields:
            # Fallback: use entire record
            record_str = json.dumps(record, sort_keys=True)
            return hashlib.md5(record_str.encode()).hexdigest()
        
        # Build checksum from delta comparison fields only
        checksum_data = {}
        for field in self.delta_fields:
            if field in record:
                checksum_data[field] = record[field]
        
        if not checksum_data:
            # Fallback: use entire record
            record_str = json.dumps(record, sort_keys=True)
            return hashlib.md5(record_str.encode()).hexdigest()
        
        checksum_str = json.dumps(checksum_data, sort_keys=True)
        return hashlib.md5(checksum_str.encode()).hexdigest()
    
    async def fetch_existing_records(
        self,
        primary_keys: List[str]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Fetch existing records from database by primary keys.
        
        Args:
            primary_keys: List of primary keys to fetch
        
        Returns:
            Dict mapping primary_key -> record data
        """
        if not primary_keys:
            return {}
        
        pool = get_pool()
        existing = {}
        
        async with pool.acquire() as conn:
            # Query api_connector_data table
            # Primary key is stored in primary_key column
            # Use ANY with array parameter for efficient lookup
            if not primary_keys:
                return {}
            
            rows = await conn.fetch("""
                SELECT 
                    id,
                    data,
                    timestamp as updated_at,
                    primary_key,
                    (data->>'checksum')::text as checksum
                FROM api_connector_data
                WHERE connector_id = $1
                  AND primary_key = ANY($2::text[])
            """, self.connector_id, primary_keys)
            
            for row in rows:
                primary_key = row.get('primary_key')
                if primary_key:
                    existing[primary_key] = {
                        'id': row['id'],
                        'data': row['data'],
                        'updated_at': row['updated_at'],
                        'checksum': row.get('checksum'),
                    }
        
        return existing
    
    def compare_records(
        self,
        incoming_record: Dict[str, Any],
        existing_record: Optional[Dict[str, Any]],
        incoming_checksum: str,
        incoming_timestamp: datetime
    ) -> Tuple[DeltaType, bool]:
        """
        Compare incoming record with existing record to determine delta type.
        
        Args:
            incoming_record: New record from API
            existing_record: Existing record from database (or None)
            incoming_checksum: Checksum of incoming record
            incoming_timestamp: Timestamp of incoming record
        
        Returns:
            Tuple of (DeltaType, should_process)
        """
        # Case 1: Record does not exist in DB
        if not existing_record:
            return (DeltaType.NEW, True)
        
        # Case 2: Record exists - compare checksum
        existing_checksum = existing_record.get('checksum')
        existing_timestamp = existing_record.get('updated_at')
        
        # If checksums match, record is unchanged
        if existing_checksum and incoming_checksum == existing_checksum:
            return (DeltaType.UNCHANGED, False)
        
        # If checksums don't match, record is updated
        # Also check timestamp if available
        if existing_timestamp and incoming_timestamp:
            if incoming_timestamp > existing_timestamp:
                return (DeltaType.UPDATED, True)
        
        # Default: treat as updated if checksum differs
        return (DeltaType.UPDATED, True)
    
    async def process_delta_batch(
        self,
        transformed_data: List[Dict[str, Any]],
        ingestion_timestamp: datetime,
        pipeline_run_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Process a batch of transformed records using delta logic.
        
        Args:
            transformed_data: List of transformed records
            ingestion_timestamp: Timestamp when data was ingested
            pipeline_run_id: Optional pipeline run ID for tracking
        
        Returns:
            Dict with processing results:
            {
                "new_count": int,
                "updated_count": int,
                "unchanged_count": int,
                "total_processed": int,
                "records": List[Dict]  # Records to process
            }
        """
        if not transformed_data:
            return {
                "new_count": 0,
                "updated_count": 0,
                "unchanged_count": 0,
                "total_processed": 0,
                "records": []
            }
        
        # Step 1: Build primary keys and checksums for all records
        records_with_keys = []
        primary_keys_to_fetch = []
        
        for record in transformed_data:
            primary_key = self.build_primary_key(record)
            checksum = self.build_checksum(record)
            
            if not primary_key:
                logger.warning(f"[DELTA] Skipping record without primary key: {record}")
                continue
            
            records_with_keys.append({
                "record": record,
                "primary_key": primary_key,
                "checksum": checksum,
            })
            primary_keys_to_fetch.append(primary_key)
        
        # Step 2: Fetch existing records from database
        existing_records = await self.fetch_existing_records(primary_keys_to_fetch)
        
        # Step 3: Compare and classify records
        new_records = []
        updated_records = []
        unchanged_count = 0
        
        for item in records_with_keys:
            record = item["record"]
            primary_key = item["primary_key"]
            checksum = item["checksum"]
            
            existing = existing_records.get(primary_key)
            delta_type, should_process = self.compare_records(
                record, existing, checksum, ingestion_timestamp
            )
            
            # Add delta metadata to record
            record["_delta_metadata"] = {
                "primary_key": primary_key,
                "checksum": checksum,
                "delta_type": delta_type.value,
                "pipeline_run_id": pipeline_run_id,
                "processed_at": ingestion_timestamp.isoformat(),
            }
            
            if delta_type == DeltaType.NEW:
                new_records.append(record)
            elif delta_type == DeltaType.UPDATED:
                updated_records.append(record)
            else:
                unchanged_count += 1
        
        total_processed = len(new_records) + len(updated_records)
        
        logger.info(
            f"[DELTA] {self.connector_id}: NEW={len(new_records)}, "
            f"UPDATED={len(updated_records)}, UNCHANGED={unchanged_count}"
        )
        
        return {
            "new_count": len(new_records),
            "updated_count": len(updated_records),
            "unchanged_count": unchanged_count,
            "total_processed": total_processed,
            "records": new_records + updated_records,  # Combined list for processing
        }


async def process_api_data_with_delta(
    connector_id: str,
    raw_api_response: Any,
    ingestion_timestamp: datetime,
    pipeline_run_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Main entry point for delta processing.
    Transforms API response and processes delta.
    
    Args:
        connector_id: API connector identifier
        raw_api_response: Raw API response
        ingestion_timestamp: Timestamp when data was ingested
        pipeline_run_id: Optional pipeline run ID
    
    Returns:
        Dict with processing results and records to save
    """
    # Step 1: Transform API response to include only required fields
    transformed = transform_api_response(connector_id, raw_api_response, ingestion_timestamp)
    transformed_records = transformed.get("transformed_data", [])
    
    if not transformed_records:
        logger.warning(f"[DELTA] No transformed records for {connector_id}")
        return {
            "new_count": 0,
            "updated_count": 0,
            "unchanged_count": 0,
            "total_processed": 0,
            "records": []
        }
    
    # Step 2: Process delta
    processor = DeltaProcessor(connector_id)
    delta_result = await processor.process_delta_batch(
        transformed_records,
        ingestion_timestamp,
        pipeline_run_id
    )
    
    return delta_result

