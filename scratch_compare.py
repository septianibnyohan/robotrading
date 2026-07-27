import sys
import os
import pandas as pd
import numpy as np
import MetaTrader5 as mt5
from datetime import datetime, timezone, timedelta

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import btc_config
from scripts.backtest_layer_bot import load_data, run_simulation

def reconstruct_real_baskets(symbol, start_time, end_time):
    """Reconstructs basket history from real MT5 deals."""
    if not mt5.initialize():
        print("Failed to initialize MT5")
        return []
        
    deals = mt5.history_deals_get(start_time, end_time)
    if not deals:
        print("No deals found in history.")
        return []
        
    # Filter deals for symbol
    symbol_deals = [d for d in deals if d.symbol == symbol]
    # Sort by time, then by ticket/id to resolve same-second entries
    symbol_deals.sort(key=lambda x: (x.time, x.ticket))
    
    baskets = []
    open_positions = {} # position_id -> deal
    current_basket = []
    max_layers = 0
    
    for d in symbol_deals:
        # Check entry type
        if d.entry == mt5.DEAL_ENTRY_IN:
            open_positions[d.position_id] = d
            current_basket.append(d)
            if len(open_positions) > max_layers:
                max_layers = len(open_positions)
        elif d.entry == mt5.DEAL_ENTRY_OUT or d.entry == mt5.DEAL_ENTRY_INOUT:
            # Position closed
            if d.position_id in open_positions:
                current_basket.append(d)
                open_positions.pop(d.position_id)
                
            if len(open_positions) == 0 and current_basket:
                # Basket fully closed
                first_entry = min(x for x in current_basket if x.entry == mt5.DEAL_ENTRY_IN)
                first_open_time = datetime.fromtimestamp(first_entry.time, timezone.utc).replace(tzinfo=None)
                last_exit = max(x for x in current_basket if x.entry in [mt5.DEAL_ENTRY_OUT, mt5.DEAL_ENTRY_INOUT])
                closed_time = datetime.fromtimestamp(last_exit.time, timezone.utc).replace(tzinfo=None)
                
                # Sum pnl
                basket_pnl = sum((x.profit + x.swap + x.commission) for x in current_basket if x.entry in [mt5.DEAL_ENTRY_OUT, mt5.DEAL_ENTRY_INOUT])
                
                baskets.append({
                    "open_time": first_open_time,
                    "close_time": closed_time,
                    "max_layers": max_layers,
                    "pnl": basket_pnl,
                    "trades_count": max_layers
                })
                current_basket = []
                max_layers = 0
                
    return baskets

def run_comparison():
    symbol = "BTCUSDc"
    
    # 1. Fetch real baskets for last 30 days
    now = datetime.now(timezone.utc)
    start_time = now - timedelta(days=30)
    
    print("Fetching Exness transaction history from MT5...")
    real_baskets = reconstruct_real_baskets(symbol, start_time, now)
    
    print(f"\nReconstructed {len(real_baskets)} baskets from Exness history:")
    real_df = pd.DataFrame(real_baskets)
    if not real_df.empty:
        # Save a copy of real baskets to inspect
        real_df.to_csv("real_baskets_1m.csv", index=False)
        print(f"Loaded {len(real_df)} baskets.")
    else:
        print("No baskets reconstructed.")
        
    # 2. Run simulation for the same period
    # Let's count minutes for 30 days
    limit = 30 * 24 * 60 + 2000
    
    # Run backtest with current config (spread 0.15)
    print("\nRunning backtest simulation with Spread $0.15...")
    btc_config.set_active_symbol(symbol)
    import importlib
    symbol_module = importlib.import_module("config.symbols.BTCUSDc")
    
    # Set to 0.15 first
    symbol_module.SPREAD_DEDUCTION_USD = 0.15
    m1_df, m5_df, h1_df = load_data(symbol, use_mt5=True, limit=limit)
    if m1_df is None or len(m1_df) == 0:
        print("Failed to load data for simulation.")
        return
        
    # Run simulation
    trades_015, _, _ = run_simulation(symbol, m1_df.copy(), m5_df.copy(), h1_df.copy())
    trades_df_015 = pd.DataFrame(trades_015)
    
    # Reconstruct baskets in memory
    if not trades_df_015.empty:
        sim_baskets_015 = trades_df_015.groupby('exit_time').agg(
            first_trade_open_time=('entry_time', 'min'),
            closed_time=('exit_time', 'first'),
            direction=('type', 'first'),
            total_layers=('basket_layers', 'max'),
            total_pnl=('pnl', 'sum')
        ).reset_index(drop=True)
    else:
        sim_baskets_015 = pd.DataFrame()
        
    # Run backtest with spread 10.0
    print("\nRunning backtest simulation with Spread $10.00...")
    symbol_module.SPREAD_DEDUCTION_USD = 10.0
    trades_10, _, _ = run_simulation(symbol, m1_df.copy(), m5_df.copy(), h1_df.copy())
    trades_df_10 = pd.DataFrame(trades_10)
    
    if not trades_df_10.empty:
        sim_baskets_10 = trades_df_10.groupby('exit_time').agg(
            first_trade_open_time=('entry_time', 'min'),
            closed_time=('exit_time', 'first'),
            direction=('type', 'first'),
            total_layers=('basket_layers', 'max'),
            total_pnl=('pnl', 'sum')
        ).reset_index(drop=True)
    else:
        sim_baskets_10 = pd.DataFrame()
        
    # Restore original spread
    symbol_module.SPREAD_DEDUCTION_USD = 0.15
    
    # 3. Print side-by-side comparison
    print("\n" + "="*60)
    print("          7-DAY PERFORMANCE COMPARISON SUMMARY")
    print("="*60)
    
    real_pnl = real_df['pnl'].sum() if not real_df.empty else 0.0
    real_max_layers = real_df['max_layers'].max() if not real_df.empty else 0
    real_avg_layers = real_df['max_layers'].mean() if not real_df.empty else 0.0
    
    sim_pnl_015 = sim_baskets_015['total_pnl'].sum() if not sim_baskets_015.empty else 0.0
    sim_max_layers_015 = sim_baskets_015['total_layers'].max() if not sim_baskets_015.empty else 0
    sim_avg_layers_015 = sim_baskets_015['total_layers'].mean() if not sim_baskets_015.empty else 0.0
    
    sim_pnl_10 = sim_baskets_10['total_pnl'].sum() if not sim_baskets_10.empty else 0.0
    sim_max_layers_10 = sim_baskets_10['total_layers'].max() if not sim_baskets_10.empty else 0
    sim_avg_layers_10 = sim_baskets_10['total_layers'].mean() if not sim_baskets_10.empty else 0.0
    
    print(f"{'Metric':25s} | {'Exness (Real)':15s} | {'Sim (Spread $0.15)':18s} | {'Sim (Spread $10)':18s}")
    print("-" * 85)
    print(f"{'Baskets Closed':25s} | {len(real_baskets):15d} | {len(sim_baskets_015):18d} | {len(sim_baskets_10):18d}")
    print(f"{'Net Profit (USD)':25s} | {real_pnl:14.2f}$ | {sim_pnl_015:17.2f}$ | {sim_pnl_10:17.2f}$")
    print(f"{'Max Layers Reached':25s} | {real_max_layers:15d} | {sim_max_layers_015:18d} | {sim_max_layers_10:18d}")
    print(f"{'Average Layers/Basket':25s} | {real_avg_layers:15.2f} | {sim_avg_layers_015:18.2f} | {sim_avg_layers_10:18.2f}")
    print("=" * 85)
    
if __name__ == "__main__":
    run_comparison()
