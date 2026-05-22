import sys
import os
import pandas as pd
import numpy as np
import pandas_ta as ta

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data.storage import DataStorage
from strategies.sma_momentum import SMAMomentumStrategy

def main():
    print("Starting Indicator Benchmarking...")

    storage = DataStorage()
    df = storage.load_rates('BTCUSD', 1, limit=1000)
    
    if df.empty:
        print("No data found.")
        return
        
    df = df.sort_values('time').reset_index(drop=True)
    
    # 1. Hand-coded implementation
    strategy = SMAMomentumStrategy(fast_window=10, slow_window=50, rsi_window=14)
    df_hand = strategy.calculate_indicators(df)
    
    # 2. pandas_ta implementation
    df_ta = df.copy()
    df_ta['sma_fast_ta'] = ta.sma(df_ta['close'], length=10)
    df_ta['sma_slow_ta'] = ta.sma(df_ta['close'], length=50)
    df_ta['rsi_ta'] = ta.rsi(df_ta['close'], length=14)
    
    # Compare
    comparison = pd.DataFrame({
        'time': df_hand['time'],
        'sma_fast_diff': (df_hand['sma_fast'] - df_ta['sma_fast_ta']).abs(),
        'sma_slow_diff': (df_hand['sma_slow'] - df_ta['sma_slow_ta']).abs(),
        'rsi_diff': (df_hand['rsi'] - df_ta['rsi_ta']).abs()
    })
    
    print("\nMean Absolute Errors (MAE) vs pandas_ta:")
    print(comparison[['sma_fast_diff', 'sma_slow_diff', 'rsi_diff']].mean())
    
    print("\nMax Absolute Errors:")
    print(comparison[['sma_fast_diff', 'sma_slow_diff', 'rsi_diff']].max())

if __name__ == "__main__":
    main()
