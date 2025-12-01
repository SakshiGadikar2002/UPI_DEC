-- Method 1: Use LIMIT to see more rows (replace 10000 with any number you want)
SELECT * FROM public.websocket_messages
ORDER BY id ASC
LIMIT 10000;

-- Method 2: See ALL rows (remove LIMIT completely)
SELECT * FROM public.websocket_messages
ORDER BY id ASC;

-- Method 3: Use pagination - see rows 1001 to 2000
SELECT * FROM public.websocket_messages
ORDER BY id ASC
LIMIT 1000 OFFSET 1000;

-- Method 4: See rows 2001 to 3000
SELECT * FROM public.websocket_messages
ORDER BY id ASC
LIMIT 1000 OFFSET 2000;

-- Method 5: Export to see all - Count first
SELECT COUNT(*) as total_messages FROM public.websocket_messages;

