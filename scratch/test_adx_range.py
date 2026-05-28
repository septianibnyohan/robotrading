import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
from btc_indicators import calculate_m5_indicators

def main():
    # Create mock data with strong trends and check ADX output range
    np.random.seed(42)
    closes = np.linspace(100, 200, 100) + np.random.randn(100) * 2
    highs = closes + np.random.rand(100) * 3
    lows = closes - np.random.rand(100) * 3
    
    df = pd.DataFrame({
        'time': pd.date_range('2026-01-01', periods=100, freq='5min'),
        'open': closes - 0.5,
        'high': highs,
        'low': lows,
        'close': closes,
        'tick_volume': np.random.randint(10, 100, 100)
    })
    
    result = calculate_m5_indicators(df)
    adx_values = result['adx_14'].dropna()
    
    print("--- ADX verification ---")
    print(f"Min ADX: {adx_values.min():.2f}")
    print(f"Max ADX: {adx_values.max():.2f}")
    print(f"ADX values: \n{adx_values.tail().to_string()}")
    
    is_valid = ((adx_values >= 0) & (adx_values <= 100)).all()
    if is_valid:
        print("[OK] All ADX values are within the valid [0, 100] range.")
    else:
        print("[ERROR] Found ADX values outside [0, 100] range!")

if __name__ == "__main__":
    main()
