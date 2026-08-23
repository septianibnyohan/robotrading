import requests
import json

def test_endpoints():
    print("Testing DXY Frontend Proxy endpoints...")
    base_url = "http://127.0.0.1:8000"
    
    # 1. Test DXY Latest endpoint
    try:
        r = requests.get(f"{base_url}/api/dxy/latest", timeout=3)
        print(f"GET /api/dxy/latest: Status Code = {r.status_code}")
        print(f"Response: {r.json() if r.status_code == 200 else r.text}\n")
    except Exception as e:
        print(f"GET /api/dxy/latest failed to connect: {e}\n")

    # 2. Test restored Frontend DXY endpoint
    try:
        r = requests.get(f"{base_url}/api/market/dxy", timeout=3)
        print(f"GET /api/market/dxy (Frontend Latest): Status Code = {r.status_code}")
        print(f"Response: {r.json() if r.status_code == 200 else r.text}\n")
    except Exception as e:
        print(f"GET /api/market/dxy failed to connect: {e}\n")
        
    # 3. Test restored Frontend DXY history endpoint
    try:
        r = requests.get(f"{base_url}/api/market/dxy/history?range=7d", timeout=3)
        print(f"GET /api/market/dxy/history?range=7d: Status Code = {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            print(f"Response: successfully retrieved {len(data)} bars. Latest bar: {data[-1] if data else 'None'}\n")
        else:
            print(f"Response: {r.text}\n")
    except Exception as e:
        print(f"GET /api/market/dxy/history failed to connect: {e}\n")

if __name__ == "__main__":
    test_endpoints()
