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



--This will show, for each connector, the URL it’s calling, the detected exchange name,
SELECT
  d.connector_id,
  c.api_url,
  d.exchange,
  COUNT(*) AS row_count
FROM api_connector_data AS d
JOIN api_connectors AS c
  ON d.connector_id = c.connector_id
GROUP BY
  d.connector_id,
  c.api_url,
  d.exchange
ORDER BY
  d.connector_id,
  d.exchange;