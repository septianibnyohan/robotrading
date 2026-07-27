import sys
import os
import pandas as pd
import numpy as np

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import btc_config
from scripts.backtest_layer_bot import load_data

print("Loading BTCUSDc data...")
m1_df, m5_df, h1_df = load_data("BTCUSDc", use_mt5=True, limit=4420875)

# Calculate indicators
from btc_indicators import calculate_h1_layer_indicators, calculate_m1_layer_indicators
h1_df = calculate_h1_layer_indicators(h1_df)
m5_df = calculate_m1_layer_indicators(m5_df)
m1_df = calculate_m1_layer_indicators(m1_df)

print("=== CHECKING FOR NaNs ===")
print("M1 close NaN count:", m1_df['close'].isna().sum())
print("M1 rsi_14 NaN count:", m1_df['rsi_14'].isna().sum())
print("M5 rsi_14 NaN count:", m5_df['rsi_14'].isna().sum())
print("H1 ema_200 NaN count:", h1_df['ema_200'].isna().sum())

# Print first valid values
print("\nM1 rsi_14 first non-NaN index:", m1_df['rsi_14'].first_valid_index())
print("H1 ema_200 first non-NaN index:", h1_df['ema_200'].first_valid_index())

# Check how many M5 crossover signals are generated in the entire dataset
print("\n=== CROSSOVER SIGNAL TEST ===")
rsi_limit_down_m1 = getattr(btc_config, 'RSI_LIMIT_DOWN_M1', 20)
rsi_limit_up_m1 = getattr(btc_config, 'RSI_LIMIT_UP_M1', 80)

m5_prev = m5_df['rsi_14'].shift(1)
m5_buy_signals = (m5_prev <= rsi_limit_down_m1) & (m5_df['rsi_14'] > rsi_limit_down_m1)
m5_sell_signals = (m5_prev >= rsi_limit_up_m1) & (m5_df['rsi_14'] < rsi_limit_up_m1)

print(f"Total M5 Buy signals: {m5_buy_signals.sum()}")
print(f"Total M5 Sell signals: {m5_sell_signals.sum()}")

m1_prev = m1_df['rsi_14'].shift(1)
m1_buy_signals = (m1_prev <= rsi_limit_down_m1) & (m1_df['rsi_14'] > rsi_limit_down_m1)
m1_sell_signals = (m1_prev >= rsi_limit_up_m1) & (m1_df['rsi_14'] < rsi_limit_up_m1)

print(f"Total M1 Buy signals: {m1_buy_signals.sum()}")
print(f"Total M1 Sell signals: {m1_sell_signals.sum()}")

# Print timestamp of some signals
if m5_buy_signals.sum() > 0:
    print("\nSome M5 Buy signals times:")
    print(m5_df[m5_buy_signals]['time'].head(10))
    print(m5_df[m5_buy_signals]['time'].tail(10))
