import sys
import os
import pandas as pd
import numpy as np

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import btc_config
from scripts.backtest_layer_bot import load_data, get_layer_step_val
from btc_indicators import calculate_h1_layer_indicators, calculate_m1_layer_indicators

print("Loading data...")
m1_df, m5_df, h1_df = load_data("BTCUSDc", use_mt5=True, limit=4420875)

h1_df = calculate_h1_layer_indicators(h1_df)
m5_df = calculate_m1_layer_indicators(m5_df)
m1_df = calculate_m1_layer_indicators(m1_df)

h1_times = h1_df['time'].values
m5_times = m5_df['time'].values
m1_times = m1_df['time'].values
timeline_times = m1_df['time'].values

print("\nChecking alignment at different loop indices:")
for i in [10, 5000, 10000, 50000, 100000, 500000, 1000000, 2000000, 3000000, 4000000]:
    if i >= len(m1_df):
        break
    t_np = timeline_times[i]
    
    idx_h1 = np.searchsorted(h1_times, t_np - np.timedelta64(1, 'h'), side='right') - 1
    idx_m5 = np.searchsorted(m5_times, t_np - np.timedelta64(5, 'm'), side='right') - 1
    idx_m1 = np.searchsorted(m1_times, t_np - np.timedelta64(1, 'm'), side='right') - 1
    
    skip = idx_h1 < 0 or idx_m5 < 1 or idx_m1 < 1
    print(f"Index {i:7d} | Time: {pd.Timestamp(t_np)} | idx_h1: {idx_h1:5d}, idx_m5: {idx_m5:5d}, idx_m1: {idx_m1:5d} | Skip: {skip}")

# Let's inspect the exact values near where trading stopped (Feb 16, 2018)
# We find the M1 index for 2018-02-16 11:13:00
idx_stop = m1_df[m1_df['time'] >= '2018-02-16 11:13:00'].index[0]
print(f"\nIndex of last trade (2018-02-16 11:13:00): {idx_stop}")

print("\nTracing loop steps around the stop index:")
for i in range(idx_stop - 5, idx_stop + 30):
    t_np = timeline_times[i]
    idx_h1 = np.searchsorted(h1_times, t_np - np.timedelta64(1, 'h'), side='right') - 1
    idx_m5 = np.searchsorted(m5_times, t_np - np.timedelta64(5, 'm'), side='right') - 1
    idx_m1 = np.searchsorted(m1_times, t_np - np.timedelta64(1, 'm'), side='right') - 1
    
    skip = idx_h1 < 0 or idx_m5 < 1 or idx_m1 < 1
    
    h1_signal = None
    m5_signal = None
    m1_signal = None
    
    if not skip:
        h1_row = h1_df.iloc[idx_h1]
        h1_close, h1_ema = h1_row['close'], h1_row['ema_200']
        h1_signal = "BUY" if h1_close > h1_ema else ("SELL" if h1_close < h1_ema else None)
        
        m5_curr = m5_df.iloc[idx_m5]
        m5_prev = m5_df.iloc[idx_m5 - 1]
        m5_buy = m5_prev['rsi_14'] <= 20 < m5_curr['rsi_14']
        m5_sell = m5_prev['rsi_14'] >= 80 > m5_curr['rsi_14']
        m5_signal = "BUY" if m5_buy else ("SELL" if m5_sell else None)
        
        m1_curr = m1_df.iloc[idx_m1]
        m1_prev = m1_df.iloc[idx_m1 - 1]
        m1_buy = m1_prev['rsi_14'] <= 20 < m1_curr['rsi_14']
        m1_sell = m1_prev['rsi_14'] >= 80 > m1_curr['rsi_14']
        m1_signal = "BUY" if m1_buy else ("SELL" if m1_sell else None)

    print(f"i: {i:6d} | Time: {pd.Timestamp(t_np)} | Skip: {skip} | H1: {h1_signal}, M5: {m5_signal}, M1: {m1_signal}")
