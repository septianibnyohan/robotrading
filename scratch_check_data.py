import sys
import os
import pandas as pd
import numpy as np

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import btc_config
from scripts.backtest_layer_bot import load_data

print("Loading BTCUSDc data from MT5 (limit 4,420,875)...")
m1_df, m5_df, h1_df = load_data("BTCUSDc", use_mt5=True, limit=4420875)

print("\n=== DATA FRAMES SHAPE ===")
print("M1 shape:", m1_df.shape if m1_df is not None else "None")
print("M5 shape:", m5_df.shape if m5_df is not None else "None")
print("H1 shape:", h1_df.shape if h1_df is not None else "None")

if m1_df is not None:
    print("\n=== M1 TIME RANGE ===")
    print("Start:", m1_df['time'].min())
    print("End:", m1_df['time'].max())
    print("NaN times in M1:", m1_df['time'].isna().sum())

if m5_df is not None:
    print("\n=== M5 TIME RANGE ===")
    print("Start:", m5_df['time'].min())
    print("End:", m5_df['time'].max())
    print("NaN times in M5:", m5_df['time'].isna().sum())

if h1_df is not None:
    print("\n=== H1 TIME RANGE ===")
    print("Start:", h1_df['time'].min())
    print("End:", h1_df['time'].max())
    print("NaN times in H1:", h1_df['time'].isna().sum())

# Check alignment by searchsorted
print("\n=== ALIGNMENT TEST ===")
t_sample = m1_df['time'].iloc[100000]
print(f"Sample M1 time: {t_sample}")
idx_m5 = np.searchsorted(m5_df['time'].values, t_sample - np.timedelta64(5, 'm'), side='right') - 1
print(f"Found M5 index: {idx_m5}")
if idx_m5 >= 0:
    print(f"Corresponding M5 time: {m5_df['time'].iloc[idx_m5]}")
