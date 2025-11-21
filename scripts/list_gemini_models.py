import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()
KEY = os.getenv('GEMINI_API_KEY')
if not KEY:
    print('GEMINI_API_KEY not set')
    raise SystemExit(1)

url = f"https://generativelanguage.googleapis.com/v1beta/models?key={KEY}"
print('Calling ListModels...')
resp = requests.get(url)
print('Status:', resp.status_code)
try:
    j = resp.json()
    print(json.dumps(j, indent=2))
except Exception as e:
    print('Failed to parse JSON:', e)
    print(resp.text)
