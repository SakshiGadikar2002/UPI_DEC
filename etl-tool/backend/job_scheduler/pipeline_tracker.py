import asyncio
import logging
import datetime
from database import get_pool

logger = logging.getLogger(__name__)

async def start_pipeline_tracker(loop):
    """Start the pipeline tracker background task"""
    logger.info("[TRACKER] Starting pipeline tracker job (every 60s)")
    loop.create_task(_tracker_loop())

async def _tracker_loop():
    """Run track_pipelines every 60 seconds"""
    while True:
        try:
            await track_pipelines()
        except Exception as e:
            logger.error(f"[TRACKER] Error in tracker loop: {e}")
        
        # Sleep for 60 seconds
        await asyncio.sleep(60)

async def track_pipelines():
    """
    Calculate ETL counts and update pipeline_steps table.
    Runs every 60 seconds.
    """
    pool = get_pool()
    if not pool:
        logger.warning("[TRACKER] Database pool not available yet")
        return

    logger.info("[TRACKER] Updating pipeline steps...")
    
    async with pool.acquire() as conn:
        try:
            # 1. Get active pipelines (connectors)
            connectors = await conn.fetch("""
                SELECT connector_id, name 
                FROM api_connectors 
                WHERE status IN ('active', 'running', 'started', 'enabled')
            """)
            
            for connector in connectors:
                connector_id = connector['connector_id']
                
                # Start transaction for this pipeline update
                async with conn.transaction():
                    # Set status to RUNNING initially (or update if exists)
                    # We use upsert here
                    await conn.execute("""
                        INSERT INTO pipeline_steps (pipeline_name, status, last_run_at)
                        VALUES ($1, 'RUNNING', NOW())
                        ON CONFLICT (pipeline_name) 
                        DO UPDATE SET status = 'RUNNING', last_run_at = NOW()
                    """, connector_id)
                    
                    # 2. Calculate Counts
                    
                    # Extract Count: Total raw responses in api_connector_data
                    extract_count = await conn.fetchval("""
                        SELECT COUNT(*) FROM api_connector_data WHERE connector_id = $1
                    """, connector_id) or 0
                    
                    # Transform Count: Total parsed items in api_connector_items
                    # We assume items in this table are "Transformed"
                    transform_count = await conn.fetchval("""
                        SELECT COUNT(*) FROM api_connector_items WHERE connector_id = $1
                    """, connector_id) or 0
                    
                    # Load Count: Total items loaded (same as transform for now as they are saved to DB)
                    # User said "Fetch load count from final visualization table" which is api_connector_items
                    load_count = transform_count
                    
                    # 3. Update pipeline_steps with counts and COMPLETED status
                    await conn.execute("""
                        UPDATE pipeline_steps 
                        SET extract_count = $1,
                            transform_count = $2,
                            load_count = $3,
                            status = 'COMPLETED'
                        WHERE pipeline_name = $4
                    """, extract_count, transform_count, load_count, connector_id)
                    
                    logger.info(f"[TRACKER] Updated {connector_id}: E={extract_count}, T={transform_count}, L={load_count}")
                    
        except Exception as e:
            logger.error(f"[TRACKER] Failed to update pipeline steps: {e}")
