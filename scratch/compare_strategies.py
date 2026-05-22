import sys
import os
sys.path.append(os.getcwd())

import pandas as pd
import numpy as np
from strategies.sma_momentum import SMAMomentumStrategy
from strategies.vbt_strategy import VBTsmaMomentum

def run_comparison():
    print("Comparing Manual vs VectorBT strategy signals...")
    
    # Create some mock trend data
    t = np.linspace(0, 100, 500)
    price = 100 + np.cumsum(np.random.normal(0.1, 1, 500))
    df = pd.DataFrame({
        'time': pd.date_range('2024-01-01', periods=500, freq='h'),
        'close': price
    })
    
    # 1. Manual Implementation
    manual_strat = SMAMomentumStrategy(fast_window=10, slow_window=50, rsi_window=14)
    # Manual strategy needs 'time' column and returns a full dataframe
    manual_df = manual_strat.generate_signals(df.copy())
    
    # 2. VectorBT Implementation
    vbt_strat = VBTsmaMomentum(fast_window=10, slow_window=50, rsi_window=14)
    vbt_entries, vbt_exits = vbt_strat.run(df['close'])
    
    # Compare
    # In manual: signal 1 is entry, -1 is exit
    manual_entries = manual_df['signal'] == 1
    manual_exits = manual_df['signal'] == -1
    
    # VectorBT signals are boolean
    # Align indices (manual might have a different index or shifted)
    common_idx = df.index
    
    entries_match = np.all(manual_entries.values == vbt_entries.values)
    exits_match = np.all(manual_exits.values == vbt_exits.values)
    
    print(f"Entry Signals Match: {entries_match}")
    print(f"Exit Signals Match: {exits_match}")
    
    if not entries_match or not exits_match:
        diff_entries = np.where(manual_entries.values != vbt_entries.values)[0]
        print(f"Differences in entries at indices: {diff_entries[:10]}")
        
    # Test Broadcasting
    print("\nTesting Broadcasting with multiple fast windows...")
    vbt_strat_broad = VBTsmaMomentum(fast_window=[10, 20], slow_window=50, rsi_window=14)
    broad_entries, _ = vbt_strat_broad.run(df['close'])
    print(f"Broadcasting output shape: {broad_entries.shape}")
    print(f"Columns: {broad_entries.columns.tolist()}")

if __name__ == "__main__":
    run_comparison()
    print("\nVerification Complete.")
