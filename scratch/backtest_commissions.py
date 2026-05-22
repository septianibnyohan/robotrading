import sys
import os
sys.path.append(os.getcwd())

import pandas as pd
import numpy as np
from strategies.vbt_strategy import VBTsmaMomentum

def test_commissions():
    print("Testing Fixed Commission Impact...")
    
    # Mock data: 1000 bars, high volatility to ensure crossovers
    price = pd.Series(1000 + np.cumsum(np.random.normal(0, 10, 1000)), name='Close')
    
    strategy = VBTsmaMomentum(fast_window=10, slow_window=50, rsi_window=14)
    
    # 1. No Commission
    pf_none = strategy.backtest(price, commission_per_lot=0.0)
    
    # 2. Raw Spread Commission (~$2 per lot)
    pf_raw = strategy.backtest(price, commission_per_lot=2.0)
    
    # 3. Zero Account Commission (~$4.375 per lot)
    pf_zero = strategy.backtest(price, commission_per_lot=4.375)
    
    print(f"\nResults Summary:")
    print(f"{'Account Type':<15} | {'Total Trades':<12} | {'Total Fees':<12} | {'Total Return':<12}")
    print("-" * 60)
    
    accounts = [
        ("No Commission", pf_none),
        ("Raw Spread ($2)", pf_raw),
        ("Zero ($4.375)", pf_zero)
    ]
    
    for name, pf in accounts:
        stats = pf.stats()
        print(f"{name:<15} | {int(stats['Total Trades']):<12} | {stats['Total Fees Paid']:<12.2f} | {stats['Total Return [%]']:<12.2f}%")

if __name__ == "__main__":
    test_commissions()
