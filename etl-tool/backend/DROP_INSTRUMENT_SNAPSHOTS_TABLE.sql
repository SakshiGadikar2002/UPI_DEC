-- SQL Script to Drop instrument_snapshots Table
-- 
-- This script removes the instrument_snapshots table and all its indexes from PostgreSQL.
-- The instrument_snapshots table has been removed from the codebase and is no longer used.
--
-- How to run:
-- 1. Open pgAdmin
-- 2. Connect to your PostgreSQL server
-- 3. Right-click on the 'etl_tool' database
-- 4. Select "Query Tool"
-- 5. Copy and paste this entire script
-- 6. Click "Execute" (F5)
--
-- OR use psql command line:
-- psql -U postgres -d etl_tool -f DROP_INSTRUMENT_SNAPSHOTS_TABLE.sql

-- Drop indexes first (they will be automatically dropped with the table, but explicit for clarity)
DROP INDEX IF EXISTS idx_instrument_snapshots_timestamp;
DROP INDEX IF EXISTS idx_instrument_snapshots_exchange;
DROP INDEX IF EXISTS idx_instrument_snapshots_instrument;
DROP INDEX IF EXISTS idx_instrument_snapshots_instrument_timestamp;

-- Drop the table (CASCADE will also drop any dependent objects)
DROP TABLE IF EXISTS instrument_snapshots CASCADE;

-- Verify table is dropped
SELECT 
    CASE 
        WHEN EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_schema = 'public'
            AND table_name = 'instrument_snapshots'
        ) 
        THEN 'Table still exists - check for errors'
        ELSE 'Table successfully dropped'
    END AS status;

