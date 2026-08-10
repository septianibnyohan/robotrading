import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def test_2y_hourly():
    ticker = "DX-Y.NYB"
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?range=730d&interval=1h"
    
    headers = {
        'User-Agent': 'Mozilla/5.0'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10, verify=False)
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            result = response.json().get("chart", {}).get("result", [])
            if result:
                timestamps = result[0].get("timestamp", [])
                print(f"Success! Fetched {len(timestamps)} bars.")
        else:
            print(response.json())
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_2y_hourly()
