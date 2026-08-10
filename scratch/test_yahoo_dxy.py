import requests
import json
import pandas as pd
from datetime import datetime
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def fetch_dxy_yahoo():
    ticker = "DX-Y.NYB"  # Yahoo Finance symbol for US Dollar Index
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?range=5d&interval=1d"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10, verify=False)
        print(f"Status Code: {response.status_code}")
        if response.status_code != 200:
            print("Failed to fetch from Yahoo Finance")
            return None
            
        data = response.json()
        result = data.get("chart", {}).get("result", [])
        if not result:
            print("No data found in response")
            return None
            
        res = result[0]
        timestamps = res.get("timestamp", [])
        indicators = res.get("indicators", {}).get("quote", [{}])[0]
        
        opens = indicators.get("open", [])
        highs = indicators.get("high", [])
        lows = indicators.get("low", [])
        closes = indicators.get("close", [])
        volumes = indicators.get("volume", [])
        
        df = pd.DataFrame({
            "timestamp": timestamps,
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": volumes
        })
        
        df["time"] = pd.to_datetime(df["timestamp"], unit="s")
        print(df.tail())
        return df
    except Exception as e:
        print(f"Error fetching DXY: {e}")
        return None

if __name__ == "__main__":
    fetch_dxy_yahoo()
