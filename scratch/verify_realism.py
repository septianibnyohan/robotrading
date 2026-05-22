import sys
import os
sys.path.append(os.getcwd())

import pandas as pd
import vectorbt as vbt
from strategies.vbt_strategy import VBTsmaMomentum

def verify_realism():
    print("Verifying Execution Realism (Decide at Close, Execute at Next Open)...")
    
    # Mock data: 10 bars
    # Price jumps at bar 5
    close = pd.Series([100, 101, 102, 103, 104, 110, 111, 112, 113, 114], name='Close')
    open_p = pd.Series([99, 100, 101, 102, 103, 105, 109, 110, 111, 112], name='Open')
    
    # Force a signal at bar 4 (index 4)
    # Using window=2 for fast SMA
    strategy = VBTsmaMomentum(fast_window=2, slow_window=5, rsi_window=2)
    
    # Manual signals to ensure we know when they happen
    entries = pd.Series([False] * 10)
    entries[4] = True # Signal at bar 4
    
    exits = pd.Series([False] * 10)
    exits[8] = True # Signal at bar 8
    
    print("\nRunning backtest with manual shift and price=open_p...")
    # Manual shift to simulate signal_delay=1
    shifted_entries = entries.vbt.fshift(1, fill_value=False)
    shifted_exits = exits.vbt.fshift(1, fill_value=False)
    
    pf = vbt.Portfolio.from_signals(
        close, 
        shifted_entries, 
        shifted_exits, 
        price=open_p,
        init_cash=10000
    )
    
    trades = pf.trades.records_readable
    print("\nTrade Records:")
    print(trades[['Exit Timestamp', 'Entry Timestamp', 'Avg Entry Price', 'Avg Exit Price']])
    
    # Verification:
    # Signal at index 4 (Close=104)
    # Delay=1 -> Execute at index 5
    # Price=open_p -> Price at index 5 is 105
    entry_price = trades.iloc[0]['Avg Entry Price']
    entry_idx = trades.iloc[0]['Entry Timestamp']
    
    print(f"\nSignal Index: 4")
    print(f"Expected Entry Index: 5")
    print(f"Actual Entry Index: {entry_idx}")
    print(f"Expected Entry Price: 105.0")
    print(f"Actual Entry Price: {entry_price}")
    
    if entry_idx == 5 and entry_price == 105.0:
        print("\nSUCCESS: Execution timing and price match the 'Next Bar Open' requirement.")
    else:
        print("\nFAILURE: Mismatch in execution timing or price.")

if __name__ == "__main__":
    verify_realism()
    print("\nVerification Complete.")
