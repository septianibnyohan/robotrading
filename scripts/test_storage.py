import os
import pandas as pd
import logging
from data.storage import DataStorage

logging.basicConfig(level=logging.INFO)

def test_data_storage():
    print("\n--- Testing DataStorage ---")
    
    # 1. Initialize Storage
    # Use a test database to avoid messing with real data
    db_path = "data/database/test_market_data.sqlite"
    if os.path.exists(db_path):
        os.remove(db_path)
        
    storage = DataStorage(db_path=db_path)
    print(f"Initialized storage at: {db_path}")

    # 2. Create Dummy Data
    dummy_data = {
        'time': [1622505600, 1622509200, 1622512800],
        'open': [35000.0, 35100.0, 34900.0],
        'high': [35200.0, 35250.0, 35050.0],
        'low': [34900.0, 34800.0, 34700.0],
        'close': [35100.0, 34900.0, 34950.0],
        'tick_volume': [1000, 1200, 1100],
        'spread': [1, 2, 1],
        'real_volume': [5000, 6000, 5500]
    }
    df = pd.DataFrame(dummy_data)
    print("\nDummy DataFrame to save:")
    print(df)

    # 3. Save Data
    symbol = "BTCUSD"
    timeframe = "H1"
    storage.save_rates(symbol, timeframe, df)
    print("\nData saved successfully.")

    # 4. Load Data
    loaded_df = storage.load_rates(symbol, timeframe)
    print("\nLoaded DataFrame from database (Should be identical or reverse ordered based on query):")
    print(loaded_df)

    # Clean up test DB
    if os.path.exists(db_path):
        os.remove(db_path)
        print(f"\nCleaned up test database at {db_path}")

if __name__ == '__main__':
    test_data_storage()
