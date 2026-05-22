import sys
import os
# Add current directory to path so we can import utils and data
sys.path.append(os.getcwd())

from utils.vbt_adapter import VBTDataLoader
import pandas as pd
import numpy as np

def test_mock_sqlite():
    print("Testing with mock data...")
    loader = VBTDataLoader(db_path="data/database/market_data.sqlite")
    
    # Try to load real data if it exists
    data = loader.from_sqlite("BTCUSD", "M15", limit=10)
    
    if data:
        print("Data loaded successfully!")
        df = data.get()
        print(f"Index type: {type(df.index)}")
        print(f"Columns: {df.columns.tolist()}")
        print(df.head())
    else:
        print("No real data found. Creating mock DataFrame to test conversion logic...")
        mock_df = pd.DataFrame({
            'time': [1715750000, 1715750900, 1715751800],
            'open': [60000, 60100, 60200],
            'high': [60200, 60300, 60400],
            'low': [59900, 60000, 60100],
            'close': [60100, 60200, 60300],
            'tick_volume': [100, 150, 200]
        })
        
        # Test the conversion logic directly
        mock_df['time'] = pd.to_datetime(mock_df['time'], unit='s', utc=True)
        mock_df.set_index('time', inplace=True)
        import vectorbt as vbt
        vbt_data = vbt.Data.from_data({'BTCUSD': mock_df}, download_kwargs={})
        print("Mock VectorBT Data created successfully!")
        print(vbt_data.get())

if __name__ == "__main__":
    test_mock_sqlite()
