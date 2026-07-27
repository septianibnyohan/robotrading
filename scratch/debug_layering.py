import sys
import os
import pandas as pd
import numpy as np

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import btc_config
from scripts.backtest_layer_bot import load_data, get_layer_step_val

symbol = "XAUUSDc"
m1_df, m5_df, h1_df = load_data(symbol, use_mt5=False, limit=500000)

print(f"Loaded {len(m1_df)} bars.")

# Calculate indicators
from btc_indicators import calculate_h1_layer_indicators, calculate_m1_layer_indicators
h1_df = calculate_h1_layer_indicators(h1_df)
m5_df = calculate_m1_layer_indicators(m5_df)
m1_df = calculate_m1_layer_indicators(m1_df)

h1_times = h1_df['time'].values
m1_times = m1_df['time'].values
timeline_times = m1_df['time'].values

import importlib
symbol_module = importlib.import_module(f"config.symbols.{symbol}")
normal_layering_step_atr_mult = getattr(symbol_module, 'LAYERING_STEP_ATR_MULT', 1.0)
low_risk_overrides = getattr(symbol_module, 'LOW_RISK_OVERRIDES', {})
moderate_risk_overrides = getattr(symbol_module, 'MODERATE_RISK_OVERRIDES', {})

# Let's run a simplified loop to find where k becomes large
positions = []
basket_direction = None
basket_first_price = 0.0
basket_risk = "normal"

for i in range(2, len(m1_df)):
    t_np = timeline_times[i]
    t = pd.Timestamp(t_np)
    bar = m1_df.iloc[i]
    
    if positions:
        # Check TP
        # (For debugging, let's keep it simple)
        pass
        
        # Layering Grid Check
        idx_h1 = np.searchsorted(h1_times, t_np - np.timedelta64(1, 'h'), side='right') - 1
        if idx_h1 >= 0:
            h1_row = h1_df.iloc[idx_h1]
            step = get_layer_step_val(h1_row, symbol, basket_risk, normal_layering_step_atr_mult, low_risk_overrides, moderate_risk_overrides)
        else:
            step = btc_config.LAYERING_STEP_USD
            
        t_wib = t.tz_localize('UTC').tz_convert('Asia/Jakarta').tz_localize(None)
        risk_level = btc_config.get_risk_level(t_wib)
        
        while True:
            k = len(positions)
            if k >= 20:
                print(f"DEBUG: k={k} reached at {t}. Bar: Close={bar['close']}, Low={bar['low']}, High={bar['high']}. Basket Direction={basket_direction}, First Price={basket_first_price}, Step={step}")
                sys.exit(0)
                
            if basket_direction == 'BUY':
                trigger_price = basket_first_price - k * step
                if bar['low'] <= trigger_price:
                    positions.append({'type': 'BUY'})
                else:
                    break
            else:
                trigger_price = basket_first_price + k * step
                if bar['high'] >= trigger_price:
                    positions.append({'type': 'SELL'})
                else:
                    break
    else:
        # Check entries
        # Let's just mock an entry to see how layering behaves
        if i == 1000:
            positions.append({'type': 'BUY'})
            basket_direction = 'BUY'
            basket_first_price = bar['open']
            basket_risk = "normal"
            print(f"Mock entry at {t}, price {basket_first_price}")
