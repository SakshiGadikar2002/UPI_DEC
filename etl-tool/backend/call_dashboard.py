import requests

try:
    r = requests.get('http://localhost:8000/api/alerts/dashboard', timeout=10)
    print('status:', r.status_code)
    try:
        print(r.json())
    except Exception:
        print(r.text)
except Exception as e:
    print('request error:', e)
