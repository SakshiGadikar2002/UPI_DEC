-- Check total number of messages in PostgreSQL
SELECT COUNT(*) as total_messages FROM websocket_messages;

-- Check messages by exchange
SELECT exchange, COUNT(*) as count 
FROM websocket_messages 
GROUP BY exchange;

-- Check recent messages (last 10)
SELECT id, timestamp, exchange, instrument, price 
FROM websocket_messages 
ORDER BY timestamp DESC 
LIMIT 10;

-- Check oldest messages (first 10)
SELECT id, timestamp, exchange, instrument, price 
FROM websocket_messages 
ORDER BY timestamp ASC 
LIMIT 10;

