"""
API Data Transformer Service

Transforms raw API responses to include only locked, required parameters.
Ensures data consistency and prepares data for delta logic.
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
import json

from services.api_parameter_schema import (
    get_api_schema,
    get_primary_identifier,
    get_business_fields,
    get_excluded_fields,
    get_delta_comparison_fields,
)

logger = logging.getLogger(__name__)


class APIDataTransformer:
    """
    Transforms API responses to include only required, locked parameters.
    Removes unnecessary fields and ensures data consistency.
    """
    
    @staticmethod
    def transform(connector_id: str, raw_data: Any, ingestion_timestamp: datetime = None) -> Dict[str, Any]:
        """
        Transform raw API response to include only required fields.
        
        Args:
            connector_id: API connector identifier
            raw_data: Raw API response (dict, list, or other)
            ingestion_timestamp: Timestamp when data was ingested (defaults to now)
        
        Returns:
            dict with structure:
            {
                "transformed_data": [...],  # Transformed records
                "metadata": {
                    "connector_id": str,
                    "timestamp": datetime,
                    "record_count": int,
                    "primary_identifier": str,
                    "delta_fields": List[str],
                }
            }
        """
        if ingestion_timestamp is None:
            ingestion_timestamp = datetime.utcnow()
        
        schema = get_api_schema(connector_id)
        if not schema:
            logger.warning(f"[TRANSFORM] No schema found for {connector_id}, storing raw data")
            return {
                "transformed_data": [{"raw": raw_data}],
                "metadata": {
                    "connector_id": connector_id,
                    "timestamp": ingestion_timestamp,
                    "record_count": 1,
                    "primary_identifier": None,
                    "delta_fields": [],
                }
            }
        
        response_type = schema.get("response_type")
        extract_rules = schema.get("extract_rules", {})
        business_fields = schema.get("business_fields", [])
        primary_identifier = schema.get("primary_identifier")
        delta_fields = schema.get("delta_comparison_fields", [])
        
        transformed_records = []
        
        try:
            if response_type == "list" and isinstance(raw_data, list):
                # Process list of items
                for item in raw_data:
                    transformed = APIDataTransformer._transform_item(
                        connector_id, item, schema, extract_rules, business_fields
                    )
                    if transformed:
                        transformed["_ingestion_timestamp"] = ingestion_timestamp.isoformat()
                        transformed_records.append(transformed)
            
            elif response_type == "dict" and isinstance(raw_data, dict):
                # Process single dict or extract from nested structure
                if connector_id == "coingecko_trending":
                    # Special handling for trending (nested structure)
                    coins = extract_rules.get("extract_coins", lambda x: [])(raw_data)
                    for coin in coins:
                        coin["_ingestion_timestamp"] = ingestion_timestamp.isoformat()
                        transformed_records.append(coin)
                
                elif connector_id == "cryptocompare_multi":
                    # Special handling for multi price (dict with symbols as keys)
                    prices = extract_rules.get("extract_prices", lambda x: [])(raw_data)
                    for price in prices:
                        price["_ingestion_timestamp"] = ingestion_timestamp.isoformat()
                        transformed_records.append(price)
                
                elif connector_id == "cryptocompare_top":
                    # Special handling for top coins (nested structure)
                    coins = extract_rules.get("extract_coins", lambda x: [])(raw_data)
                    for coin in coins:
                        coin["_ingestion_timestamp"] = ingestion_timestamp.isoformat()
                        transformed_records.append(coin)
                
                else:
                    # Standard dict processing
                    transformed = APIDataTransformer._transform_item(
                        connector_id, raw_data, schema, extract_rules, business_fields
                    )
                    if transformed:
                        transformed["_ingestion_timestamp"] = ingestion_timestamp.isoformat()
                        transformed_records.append(transformed)
            
            else:
                logger.warning(
                    f"[TRANSFORM] Unexpected data type for {connector_id}: "
                    f"expected {response_type}, got {type(raw_data).__name__}"
                )
                # Fallback: store as raw
                transformed_records.append({
                    "raw": raw_data,
                    "_ingestion_timestamp": ingestion_timestamp.isoformat()
                })
        
        except Exception as e:
            logger.error(f"[TRANSFORM] Error transforming {connector_id}: {e}", exc_info=True)
            # Fallback: store raw data
            transformed_records.append({
                "raw": raw_data,
                "_error": str(e),
                "_ingestion_timestamp": ingestion_timestamp.isoformat()
            })
        
        return {
            "transformed_data": transformed_records,
            "metadata": {
                "connector_id": connector_id,
                "timestamp": ingestion_timestamp,
                "record_count": len(transformed_records),
                "primary_identifier": primary_identifier,
                "delta_fields": delta_fields,
                "business_fields": business_fields,
            }
        }
    
    @staticmethod
    def _transform_item(
        connector_id: str,
        item: Dict[str, Any],
        schema: Dict[str, Any],
        extract_rules: Dict[str, Any],
        business_fields: List[str]
    ) -> Optional[Dict[str, Any]]:
        """
        Transform a single item using schema rules.
        
        Args:
            connector_id: API connector identifier
            item: Single item from API response
            schema: API parameter schema
            extract_rules: Extraction rules from schema
            business_fields: Required business fields
        
        Returns:
            Transformed item dict or None if transformation fails
        """
        if not isinstance(item, dict):
            return None
        
        transformed = {}
        excluded_fields = get_excluded_fields(connector_id) or []
        
        # Extract fields using extract_rules first
        for field_name, extract_func in extract_rules.items():
            try:
                if callable(extract_func):
                    value = extract_func(item)
                    if value is not None:
                        transformed[field_name] = value
                else:
                    # Direct field mapping
                    if field_name in item:
                        transformed[field_name] = item[field_name]
            except Exception as e:
                logger.debug(f"[TRANSFORM] Error extracting {field_name} for {connector_id}: {e}")
        
        # Extract required business fields
        for field_name in business_fields:
            if field_name in transformed:
                continue  # Already extracted
            
            # Handle nested fields (e.g., "item.id")
            if "." in field_name:
                parts = field_name.split(".")
                value = item
                for part in parts:
                    if isinstance(value, dict):
                        value = value.get(part)
                    else:
                        value = None
                        break
                if value is not None:
                    transformed[field_name.replace(".", "_")] = value
            elif field_name in item:
                # Check if field should be excluded
                if field_name not in excluded_fields:
                    transformed[field_name] = item[field_name]
        
        # Remove excluded fields
        for field in excluded_fields:
            transformed.pop(field, None)
        
        # Ensure primary identifier exists
        primary_id = schema.get("primary_identifier")
        if primary_id:
            if "." in primary_id:
                # Nested field, check if extracted
                primary_key = primary_id.replace(".", "_")
                if primary_key not in transformed:
                    # Try to extract it
                    parts = primary_id.split(".")
                    value = item
                    for part in parts:
                        if isinstance(value, dict):
                            value = value.get(part)
                        else:
                            value = None
                            break
                    if value is not None:
                        transformed[primary_key] = value
            elif primary_id not in transformed and primary_id in item:
                transformed[primary_id] = item[primary_id]
        
        return transformed if transformed else None
    
    @staticmethod
    def build_idempotency_key(connector_id: str, record: Dict[str, Any]) -> str:
        """
        Build idempotency key from transformed record.
        Uses primary identifier and delta comparison fields.
        
        Args:
            connector_id: API connector identifier
            record: Transformed record
        
        Returns:
            String idempotency key
        """
        schema = get_api_schema(connector_id)
        if not schema:
            # Fallback: use hash of entire record
            return str(hash(json.dumps(record, sort_keys=True)))
        
        primary_id = schema.get("primary_identifier")
        delta_fields = schema.get("delta_comparison_fields", [])
        
        key_parts = []
        
        # Add primary identifier
        if primary_id:
            if "." in primary_id:
                primary_key = primary_id.replace(".", "_")
            else:
                primary_key = primary_id
            
            primary_value = record.get(primary_key)
            if primary_value is not None:
                key_parts.append(str(primary_value))
        
        # Add delta comparison fields
        for field in delta_fields:
            if field in record:
                value = record[field]
                if value is not None:
                    key_parts.append(str(value))
        
        # If no key parts, use hash
        if not key_parts:
            return str(hash(json.dumps(record, sort_keys=True)))
        
        return "|".join(key_parts)
    
    @staticmethod
    def get_delta_marker_value(connector_id: str, record: Dict[str, Any]) -> Optional[Any]:
        """
        Extract delta marker value from transformed record.
        Uses the primary identifier or first delta comparison field.
        
        Args:
            connector_id: API connector identifier
            record: Transformed record
        
        Returns:
            Marker value (timestamp, ID, or other) or None
        """
        schema = get_api_schema(connector_id)
        if not schema:
            return None
        
        # Try to get timestamp field
        timestamp_field = schema.get("timestamp_field")
        if timestamp_field and timestamp_field in record:
            return record[timestamp_field]
        
        # Use ingestion timestamp
        if "_ingestion_timestamp" in record:
            return record["_ingestion_timestamp"]
        
        # Fallback: use primary identifier
        primary_id = schema.get("primary_identifier")
        if primary_id:
            if "." in primary_id:
                primary_key = primary_id.replace(".", "_")
            else:
                primary_key = primary_id
            
            if primary_key in record:
                return record[primary_key]
        
        return None


def transform_api_response(connector_id: str, raw_data: Any, ingestion_timestamp: datetime = None) -> Dict[str, Any]:
    """
    Convenience function to transform API response.
    
    Args:
        connector_id: API connector identifier
        raw_data: Raw API response
        ingestion_timestamp: Optional ingestion timestamp
    
    Returns:
        Transformed data structure
    """
    return APIDataTransformer.transform(connector_id, raw_data, ingestion_timestamp)

