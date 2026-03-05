
import os
import httpx
import time

# URL configurada en .env (dentro del contenedor, debe ser la interna)
# N8N_WEBHOOK_URL=http://n8n:5678/webhook/whatsapp-inbound-event
url = os.getenv("N8N_WEBHOOK_URL", "http://n8n:5678/webhook/whatsapp-inbound-event")

print(f"Testing connection to n8n at: {url}")

payload = {
    "test": "Hello from motor_api container",
    "timestamp": time.time()
}

try:
    print("Sending POST request...")
    response = httpx.post(url, json=payload, timeout=5.0)
    print(f"Response Status: {response.status_code}")
    print(f"Response Body: {response.text}")
    
    if response.status_code == 200:
        print("SUCCESS: Webhook reached successfully!")
    else:
        print("WARNING: Webhook reached but returned non-200 status.")
        
except Exception as e:
    print(f"ERROR: Failed to connect to n8n.")
    print(f"Exception: {e}")
    
    # Try just reaching the root to check connectivity
    try:
        root_url = "http://n8n:5678/"
        print(f"Trying root URL: {root_url}")
        resp = httpx.get(root_url, timeout=2.0)
        print(f"Root check status: {resp.status_code}")
    except Exception as e2:
        print(f"Root check failed: {e2}")
