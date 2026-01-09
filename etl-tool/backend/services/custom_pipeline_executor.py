"""
Custom Pipeline Execution Engine

Executes user-defined pipelines with configurable nodes and transformations.
"""

import logging
import json
from typing import Dict, List, Any, Optional
from datetime import datetime

from database import get_pool
from services.delta_integrated_save import save_to_database_with_delta

logger = logging.getLogger(__name__)


async def execute_custom_pipeline(pipeline_id: str, definition: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute a custom pipeline definition.
    
    Args:
        pipeline_id: Pipeline identifier
        definition: Pipeline definition with nodes and edges
        
    Returns:
        Execution result with record counts and status
    """
    try:
        nodes = {node["id"]: node for node in definition.get("nodes", [])}
        edges = definition.get("edges", [])
        
        # Build execution graph
        graph = _build_execution_graph(nodes, edges)
        
        # Find source node
        source_node = _find_source_node(nodes)
        if not source_node:
            raise ValueError("No source node found in pipeline")
        
        # Execute pipeline starting from source
        result = await _execute_node(source_node["id"], nodes, graph, {})
        
        return {
            "success": True,
            "pipeline_id": pipeline_id,
            "records_processed": result.get("records_processed", 0),
            "records_saved": result.get("records_saved", 0),
            "execution_time_ms": result.get("execution_time_ms", 0),
            "step_results": result.get("step_results", []),
            "final_data": result.get("data", [])[:10]  # Return first 10 records for preview
        }
    except Exception as e:
        logger.error(f"Error executing custom pipeline {pipeline_id}: {e}")
        return {
            "success": False,
            "error": str(e),
            "pipeline_id": pipeline_id
        }


def _build_execution_graph(nodes: Dict[str, Dict], edges: List[Dict]) -> Dict[str, List[str]]:
    """Build adjacency list for execution graph"""
    graph = {node_id: [] for node_id in nodes.keys()}
    for edge in edges:
        source = edge["source"]
        target = edge["target"]
        if source in graph:
            graph[source].append(target)
    return graph


def _find_source_node(nodes: Dict[str, Dict]) -> Optional[Dict]:
    """Find the source node in the pipeline"""
    for node in nodes.values():
        if node.get("type") == "source":
            return node
    return None


async def _execute_node(
    node_id: str,
    nodes: Dict[str, Dict],
    graph: Dict[str, List[str]],
    context: Dict[str, Any]
) -> Dict[str, Any]:
    """Execute a single node and propagate data to next nodes"""
    node = nodes[node_id]
    node_type = node.get("type")
    config = node.get("config", {})
    
    start_time = datetime.utcnow()
    
    # Initialize step_results if not present
    if "step_results" not in context:
        context["step_results"] = []
    
    try:
        if node_type == "source":
            data = await _execute_source_node(config)
            context["data"] = data
            context["records_processed"] = len(data) if isinstance(data, list) else 1
            context["step_results"].append({
                "node_id": node_id,
                "node_type": "source",
                "node_name": node.get("config", {}).get("connector_id", "Source"),
                "records_count": len(data) if isinstance(data, list) else 1,
                "sample_data": data[:5] if isinstance(data, list) else [data]
            })
            
        elif node_type == "field_selector":
            data = context.get("data", [])
            selected_fields = config.get("selected_fields", [])
            data = _select_fields(data, selected_fields)
            context["data"] = data
            context["step_results"].append({
                "node_id": node_id,
                "node_type": "field_selector",
                "node_name": f"Field Selector ({len(selected_fields)} fields)",
                "records_count": len(data) if isinstance(data, list) else 1,
                "selected_fields": selected_fields,
                "sample_data": data[:5] if isinstance(data, list) else [data]
            })
            
        elif node_type == "filter":
            data = context.get("data", [])
            filter_config = config.get("filter", {})
            before_count = len(data) if isinstance(data, list) else 1
            data = _apply_filter(data, filter_config)
            context["data"] = data
            after_count = len(data) if isinstance(data, list) else 1
            context["records_processed"] = after_count
            context["step_results"].append({
                "node_id": node_id,
                "node_type": "filter",
                "node_name": f"Filter: {filter_config.get('field', 'N/A')} {filter_config.get('operator', '')} {filter_config.get('value', '')}",
                "records_before": before_count,
                "records_after": after_count,
                "records_count": after_count,
                "sample_data": data[:5] if isinstance(data, list) else [data]
            })
            
        elif node_type == "transform":
            data = context.get("data", [])
            transformations = config.get("transformations", [])
            data = _apply_transformations(data, transformations)
            context["data"] = data
            context["step_results"].append({
                "node_id": node_id,
                "node_type": "transform",
                "node_name": f"Transform ({len(transformations)} transformations)",
                "records_count": len(data) if isinstance(data, list) else 1,
                "transformations": transformations,
                "sample_data": data[:5] if isinstance(data, list) else [data]
            })
            
        elif node_type == "destination":
            data = context.get("data", [])
            destination_config = config.get("destination", {})
            saved_count = await _save_to_destination(data, destination_config, config.get("connector_id"))
            context["records_saved"] = saved_count
            context["step_results"].append({
                "node_id": node_id,
                "node_type": "destination",
                "node_name": f"Destination ({destination_config.get('type', 'database')})",
                "records_count": len(data) if isinstance(data, list) else 1,
                "records_saved": saved_count,
                "sample_data": data[:5] if isinstance(data, list) else [data]
            })
            return context
        
        # Execute next nodes
        next_nodes = graph.get(node_id, [])
        for next_node_id in next_nodes:
            result = await _execute_node(next_node_id, nodes, graph, context.copy())
            context.update(result)
        
        execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
        context["execution_time_ms"] = execution_time
        
        return context
        
    except Exception as e:
        logger.error(f"Error executing node {node_id}: {e}")
        context["step_results"].append({
            "node_id": node_id,
            "node_type": node_type,
            "node_name": node.get("type", "Unknown"),
            "error": str(e),
            "status": "error"
        })
        raise


async def _execute_source_node(config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Execute source node - fetch data from connector"""
    connector_id = config.get("connector_id")
    if not connector_id:
        raise ValueError("Source node must have connector_id configured")
    
    pool = get_pool()
    async with pool.acquire() as conn:
        # Get recent data from connector
        limit = config.get("limit", 100)
        rows = await conn.fetch("""
            SELECT data, timestamp
            FROM api_connector_data
            WHERE connector_id = $1
            ORDER BY timestamp DESC
            LIMIT $2
        """, connector_id, limit)
        
        data = []
        for row in rows:
            record = row["data"] if isinstance(row["data"], dict) else json.loads(row["data"])
            record["_ingestion_timestamp"] = row["timestamp"].isoformat()
            data.append(record)
        
        return data


def _select_fields(data: List[Dict], selected_fields: List[str]) -> List[Dict]:
    """Select only specified fields from data"""
    if not selected_fields:
        return data
    
    result = []
    for record in data:
        selected = {}
        for field in selected_fields:
            # Handle nested fields (e.g., "data.price")
            parts = field.split(".")
            value = record
            for part in parts:
                if isinstance(value, dict) and part in value:
                    value = value[part]
                else:
                    value = None
                    break
            if value is not None:
                selected[field] = value
        result.append(selected)
    
    return result


def _apply_filter(data: List[Dict], filter_config: Dict[str, Any]) -> List[Dict]:
    """Apply filter conditions to data"""
    if not filter_config:
        return data
    
    field = filter_config.get("field")
    operator = filter_config.get("operator")
    value = filter_config.get("value")
    
    if not field or not operator:
        return data
    
    filtered = []
    for record in data:
        # Get field value (handle nested fields)
        parts = field.split(".")
        field_value = record
        for part in parts:
            if isinstance(field_value, dict) and part in field_value:
                field_value = field_value[part]
            else:
                field_value = None
                break
        
        # Apply operator
        if operator == "equals" and field_value == value:
            filtered.append(record)
        elif operator == "greater_than" and field_value is not None and field_value > value:
            filtered.append(record)
        elif operator == "less_than" and field_value is not None and field_value < value:
            filtered.append(record)
        elif operator == "contains" and field_value is not None and str(value) in str(field_value):
            filtered.append(record)
        elif operator == "not_equals" and field_value != value:
            filtered.append(record)
    
    return filtered


def _apply_transformations(data: List[Dict], transformations: List[Dict]) -> List[Dict]:
    """Apply transformation rules to data"""
    result = data.copy()
    
    for transformation in transformations:
        transform_type = transformation.get("type")
        
        if transform_type == "rename":
            old_name = transformation.get("old_name")
            new_name = transformation.get("new_name")
            if old_name and new_name:
                for record in result:
                    if old_name in record:
                        record[new_name] = record.pop(old_name)
        
        elif transform_type == "calculate":
            new_field = transformation.get("new_field")
            expression = transformation.get("expression")
            if new_field and expression:
                for record in result:
                    try:
                        # Simple expression evaluation (you can enhance this)
                        # For now, support basic arithmetic
                        value = eval(expression, {"__builtins__": {}}, record)
                        record[new_field] = value
                    except:
                        pass
        
        elif transform_type == "add_constant":
            field = transformation.get("field")
            value = transformation.get("value")
            if field and value is not None:
                for record in result:
                    record[field] = value
    
    return result


async def _save_to_destination(
    data: List[Dict],
    destination_config: Dict[str, Any],
    connector_id: str
) -> int:
    """Save data to destination"""
    destination_type = destination_config.get("type", "database")
    
    if destination_type == "database":
        # Use existing save logic
        saved_count = 0
        for record in data:
            message = {
                "connector_id": connector_id or "custom_pipeline",
                "data": record,
                "timestamp": record.get("_ingestion_timestamp", datetime.utcnow().isoformat()),
                "status_code": 200,
                "response_time_ms": 0
            }
            result = await save_to_database_with_delta(message)
            if result.get("records_saved", 0) > 0:
                saved_count += result["records_saved"]
        
        return saved_count
    
    return 0

