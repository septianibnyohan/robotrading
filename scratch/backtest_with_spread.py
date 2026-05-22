import sys
import os
sys.path.append(os.getcwd())

import pandas as pd
import vectorbt as vbt
from utils.vbt_adapter import VBTDataLoader
from strategies.vbt_strategy import VBTsmaMomentum

def run_real_backtest():
    print("Loading real BTCUSD data from SQLite...")
    loader = VBTDataLoader()
    
    # Load 1-minute data if possible, or whatever is available
    data = loader.from_sqlite("BTCUSD", "1", limit=5000) # '1' for M1
    
    if not data:
        print("No real data found. Using mock data for demonstration.")
        # Create mock data with spread
        price = pd.Series([60000 + i*10 + np.random.normal(0, 50) for i in range(1000)], name='Close')
        spread_points = pd.Series([200 + np.random.randint(-50, 50) for _ in range(1000)], name='Spread')
        
        # Convert points to percentage slippage
        # Assuming 1 point = 0.01 USD. So 200 points = 2 USD.
        # Slippage = (2 USD / 60000 USD) = 0.000033
        slippage_series = (spread_points * 0.01) / price
        
        strategy = VBTsmaMomentum(fast_window=10, slow_window=50, rsi_window=14)
        
        print("Running backtest with fixed slippage (0.01%)...")
        pf_fixed = strategy.backtest(price, slippage=0.0001)
        
        print("Running backtest with historical spread simulation...")
        pf_spread = strategy.backtest(price, slippage=slippage_series)
        
        print(f"\nFixed Slippage Return: {pf_fixed.total_return():.4%}")
        print(f"Spread-based Return: {pf_spread.total_return():.4%}")
        
    else:
        vbt_data = data
        close = vbt_data.get('close')
        spread = vbt_data.get('spread')
        
        # Point size for BTCUSD is typically 0.01 on MT5/Exness
        point_size = 0.01 
        slippage_series = (spread * point_size) / close
        
        strategy = VBTsmaMomentum(fast_window=10, slow_window=50, rsi_window=14)
        
        print("Running backtest with historical spreads...")
        pf = strategy.backtest(close, slippage=slippage_series)
        
        print("\nBacktest Summary:")
        print(pf.stats())

if __name__ == "__main__":
    import numpy as np
    run_real_backtest()
