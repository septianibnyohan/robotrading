import requests
import json
import pandas as pd
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def fetch_dxy_h1():
    ticker = "DX-Y.NYB"
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?range=10d&interval=1h"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10, verify=False)
        if response.status_code != 200:
            return None
            
        data = response.json()
        result = data.get("chart", {}).get("result", [])
        if not result:
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
        
        df["time"] = pd.to_datetime(df["timestamp"], unit="s", utc=True)
        print(f"Total rows fetched: {len(df)}")
        df_clean = df.dropna(subset=["open", "high", "low", "close"])
        print(f"Clean rows: {len(df_clean)}")
        print(df_clean.tail(5))
        return df_clean
    except Exception as e:
        print(f"Error: {e}")
        return None

if __name__ == "__main__":
    fetch_dxy_h1()
