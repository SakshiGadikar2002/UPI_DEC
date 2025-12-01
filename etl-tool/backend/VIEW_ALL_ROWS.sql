-- This will show ALL 7883+ rows (remove LIMIT to see everything)
-- But it might be slow, so let's do it in chunks first

-- First, let's see rows 1-5000
SELECT * FROM public.websocket_messages
ORDER BY id ASC
LIMIT 5000;

-- Then see rows 5001-7883
SELECT * FROM public.websocket_messages
ORDER BY id ASC
LIMIT 3000 OFFSET 5000;

-- OR see ALL at once (might be slow with 7883 rows)
SELECT * FROM public.websocket_messages
ORDER BY id ASC;

