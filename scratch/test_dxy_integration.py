import requests
import subprocess
import time
import sys

def test_endpoints():
    print("Testing FastAPI proxy endpoints...")
    base_url = "http://127.0.0.1:8000"
    
    # 1. Test DXY Latest endpoint
    try:
        r = requests.get(f"{base_url}/api/dxy/latest", timeout=3)
        print(f"GET /api/dxy/latest: Status Code = {r.status_code}")
        print(f"Response: {r.json() if r.status_code == 200 else r.text}")
    except Exception as e:
        print(f"GET /api/dxy/latest failed to connect: {e}")
        
    # 2. Test DXY Historical endpoint
    try:
        r = requests.get(f"{base_url}/api/dxy/historical?limit=5", timeout=3)
        print(f"GET /api/dxy/historical: Status Code = {r.status_code}")
        print(f"Response: {r.json() if r.status_code == 200 else r.text}")
    except Exception as e:
        print(f"GET /api/dxy/historical failed to connect: {e}")
        
    # 3. Test DXY Harvest endpoint
    try:
        r = requests.post(f"{base_url}/api/dxy/harvest", timeout=3)
        print(f"POST /api/dxy/harvest: Status Code = {r.status_code}")
        print(f"Response: {r.json() if r.status_code == 200 else r.text}")
    except Exception as e:
        print(f"POST /api/dxy/harvest failed to connect: {e}")

if __name__ == "__main__":
    # If python web server is not running, warn the user.
    # We will test hitting the endpoints.
    test_endpoints()
