import sys
import os
import numpy as np
import pandas as pd
import vectorbt as vbt
import random

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.storage import DataStorage
from monitoring.logger import setup_logging
from config.credentials import get_mt5_credentials

def main():
    logger = setup_logging()
    logger.info("Starting Exhaustive Grid Search with VectorBT...")

    credentials = get_mt5_credentials()
    symbol = credentials.get('symbol', 'BTCUSDm')
    
    storage = DataStorage()
    # Load a substantial amount of data for optimization
    df = storage.load_rates(symbol, 1, limit=50000)
    
    if df.empty:
        logger.error("No data found. Please run the harvester first.")
        return
        
    df['time'] = pd.to_datetime(df['time'])
    df = df.sort_values('time').set_index('time')
    
    close = df['close']
    open_price = df['open']
    
    # Define Parameter Grid
    # Fast windows from 2 to 50, step 2
    # Slow windows from 20 to 200, step 5
    # To use run_combs effectively and get all valid pairs (fast < slow),
    # we can pass a single large array of windows and let it pair them up,
    # OR we can manually create a cartesian product if we want distinct ranges.
    # The prompt explicitly suggested vbt.MA.run_combs().
    
    # Let's create a combined array of windows to sample from
    all_windows = np.unique(np.concatenate([
        np.arange(2, 52, 2),   # Fast candidates
        np.arange(20, 205, 5)  # Slow candidates
    ]))
    
    logger.info(f"Generating MA combinations from {len(all_windows)} unique window sizes...")
    
    # Subset Testing Logic (Random sampling of windows to prevent memory crash on massive grids)
    MAX_WINDOWS = 60 # limits combinations to (60*59)/2 = 1770
    if len(all_windows) > MAX_WINDOWS:
        logger.info(f"Subset Testing: Randomly sampling {MAX_WINDOWS} windows from the full set to keep memory usage manageable.")
        # Ensure we keep some small and some large windows to guarantee valid fast < slow pairs
        small_windows = all_windows[all_windows < 50]
        large_windows = all_windows[all_windows >= 50]
        
        sampled_small = np.random.choice(small_windows, size=min(len(small_windows), MAX_WINDOWS // 2), replace=False)
        sampled_large = np.random.choice(large_windows, size=min(len(large_windows), MAX_WINDOWS - len(sampled_small)), replace=False)
        
        all_windows = np.sort(np.concatenate([sampled_small, sampled_large]))

    # Run Combinatorial Sweep
    # r=2 generates all pairs (fast, slow) where fast < slow
    fast_ma, slow_ma = vbt.MA.run_combs(
        close, 
        window=all_windows, 
        r=2, 
        short_names=['fast', 'slow']
    )
    
    num_combinations = len(fast_ma.wrapper.columns)
    logger.info(f"Generated {num_combinations} unique Fast/Slow SMA combinations.")
    
    # Calculate RSI (Keeping fixed for this sweep to visualize MA interaction cleanly)
    rsi_window = 14
    rsi = vbt.RSI.run(close, window=rsi_window)
    
    # Get 1D series for RSI conditions
    rsi_series = rsi.rsi
    if isinstance(rsi_series, pd.DataFrame):
        rsi_series = rsi_series.iloc[:, 0]
        
    rsi_low = rsi_series < 70
    rsi_high = rsi_series > 85
    rsi_short_low = rsi_series > 30
    rsi_short_high = rsi_series < 15
    
    logger.info("Broadcasting signals across the parameter matrix...")
    
    # Vectorized Signal Logic across all combinations simultaneously
    # We use .mul(..., axis=0) to correctly broadcast the 1D RSI condition across the MultiIndex columns
    long_entries = fast_ma.ma_crossed_above(slow_ma).mul(rsi_low, axis=0).astype(bool)
    long_exits = fast_ma.ma_crossed_below(slow_ma).add(rsi_high, axis=0).astype(bool)
    
    short_entries = fast_ma.ma_crossed_below(slow_ma).mul(rsi_short_low, axis=0).astype(bool)
    short_exits = fast_ma.ma_crossed_above(slow_ma).add(rsi_short_high, axis=0).astype(bool)

    
    # Shift signals by 1 to execute on the next open (prevent lookahead)
    long_entries = long_entries.vbt.fshift(1, fill_value=False)
    long_exits = long_exits.vbt.fshift(1, fill_value=False)
    short_entries = short_entries.vbt.fshift(1, fill_value=False)
    short_exits = short_exits.vbt.fshift(1, fill_value=False)

    logger.info("Running parallel portfolio simulations...")
    
    portfolio = vbt.Portfolio.from_signals(
        close, 
        entries=long_entries, 
        exits=long_exits, 
        short_entries=short_entries,
        short_exits=short_exits,
        price=open_price, # Execute at Open
        init_cash=10000, 
        fees=0.0006,
        slippage=0.0001,
        freq='1m'
    )
    
    logger.info("Calculating Sharpe Ratios...")
    sharpe_ratios = portfolio.sharpe_ratio()
    
    # Generate Heatmap
    logger.info("Generating Performance Heatmap...")
    
    # Extract Fast and Slow windows from the MultiIndex for plotting
    # The columns multi-index created by run_combs looks like (fast_window, slow_window)
    # We can unstack to create a 2D matrix: rows = fast_window, cols = slow_window
    heatmap_matrix = sharpe_ratios.unstack(level='slow_window')
    
    fig = heatmap_matrix.vbt.heatmap(
        title=f"Sharpe Ratio Heatmap (RSI={rsi_window})",
        xaxis_title="Slow SMA Window",
        yaxis_title="Fast SMA Window",
        trace_kwargs=dict(colorscale='RdYlGn', zmid=0)
    )
    
    # Save Heatmap
    output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "monitoring")
    os.makedirs(output_dir, exist_ok=True)
    
    html_path = os.path.join(output_dir, "sharpe_heatmap.html")
    fig.write_html(html_path)
    
    # Print Top 5 Combinations
    print("\n" + "="*50)
    print("      TOP 5 PARAMETER COMBINATIONS")
    print("="*50)
    top_5 = sharpe_ratios.sort_values(ascending=False).head(5)
    print(top_5)
    print("="*50)
    
    logger.info(f"Heatmap successfully saved to: {html_path}")
    print(f"\nOpen {html_path} in your browser to view 'islands of profitability'.")

if __name__ == "__main__":
    main()
