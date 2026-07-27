import sys
import os
import pandas as pd
import numpy as np
import MetaTrader5 as mt5
from datetime import datetime, timezone, timedelta

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def analyze_real_spreads():
    symbol = "XAUUSDc"
    
    if not mt5.initialize():
        print("Failed to initialize MT5")
        return
        
    print("Fetching last 30 days of trade history...")
    now = datetime.now(timezone.utc)
    start_time = now - timedelta(days=30)
    
    deals = mt5.history_deals_get(start_time, now)
    if not deals:
        print("No deals found.")
        mt5.shutdown()
        return
        
    symbol_deals = [d for d in deals if d.symbol == symbol]
    print(f"Found {len(symbol_deals)} deals for {symbol}.")
    
    spreads_usd = []
    spreads_points = []
    
    info = mt5.symbol_info(symbol)
    point_size = info.point if info else 0.01
    
    print("Fetching tick data for each deal execution time (this may take a few seconds)...")
    for i, d in enumerate(symbol_deals):
        # Time of the deal
        deal_time_sec = d.time
        # Fetch a small window of ticks around this time
        # copy_ticks_from takes a datetime or timestamp
        dt = datetime.fromtimestamp(deal_time_sec, timezone.utc)
        
        # Get 10 ticks starting from deal time
        ticks = mt5.copy_ticks_from(symbol, dt - timedelta(seconds=1), 10, mt5.COPY_TICKS_ALL)
        if ticks is not None and len(ticks) > 0:
            # Find tick closest to the execution price, or just the first tick
            # Let's find the tick with the minimum time difference
            deal_time_ms = d.time_msc
            best_tick = min(ticks, key=lambda x: abs(x['time_msc'] - deal_time_ms))
            
            spread_usd = best_tick['ask'] - best_tick['bid']
            spread_pts = spread_usd / point_size
            
            spreads_usd.append(spread_usd)
            spreads_points.append(spread_pts)
            
        if (i+1) % 100 == 0:
            print(f"Processed {i+1}/{len(symbol_deals)} deals...")
            
    mt5.shutdown()
    
    if len(spreads_usd) == 0:
        print("Could not retrieve tick data for any deals.")
        return
        
    # Calculate statistics
    spreads_usd = np.array(spreads_usd)
    spreads_points = np.array(spreads_points)
    
    print("\n" + "="*50)
    print(f"       REAL SPREAD ANALYSIS FOR {symbol}")
    print("="*50)
    print(f"Total executions analyzed:  {len(spreads_usd)}")
    print(f"Average Spread:             {spreads_usd.mean():.2f} USD ({spreads_points.mean():.1f} points)")
    print(f"Median Spread (50th %):     {np.percentile(spreads_usd, 50):.2f} USD ({np.percentile(spreads_points, 50):.1f} points)")
    print(f"90th Percentile Spread:     {np.percentile(spreads_usd, 90):.2f} USD ({np.percentile(spreads_points, 90):.1f} points)")
    print(f"95th Percentile Spread:     {np.percentile(spreads_usd, 95):.2f} USD ({np.percentile(spreads_points, 95):.1f} points)")
    print(f"99th Percentile Spread:     {np.percentile(spreads_usd, 99):.2f} USD ({np.percentile(spreads_points, 99):.1f} points)")
    print(f"Minimum Spread:             {spreads_usd.min():.2f} USD ({spreads_points.min():.1f} points)")
    print(f"Maximum Spread:             {spreads_usd.max():.2f} USD ({spreads_points.max():.1f} points)")
    print("="*50)

if __name__ == "__main__":
    analyze_real_spreads()
