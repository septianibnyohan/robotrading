import MetaTrader5 as mt5
import sys
from datetime import datetime, timezone, timedelta

def main():
    if not mt5.initialize():
        print(f"Failed to initialize MT5: {mt5.last_error()}")
        sys.exit(1)
        
    symbol = "XAGUSDc"
    selected = mt5.symbol_select(symbol, True)
    if not selected:
        print(f"Failed to select symbol {symbol}: {mt5.last_error()}")
        mt5.shutdown()
        sys.exit(1)
        
    info = mt5.symbol_info(symbol)
    if not info:
        print(f"Failed to get symbol info for {symbol}")
        mt5.shutdown()
        sys.exit(1)
        
    tick = mt5.symbol_info_tick(symbol)
    if not tick:
        print(f"Failed to get symbol tick for {symbol}")
        mt5.shutdown()
        sys.exit(1)
        
    spread_usd = tick.ask - tick.bid
    spread_points = spread_usd / info.point
    
    print("\n" + "="*50)
    print(f"       CURRENT REAL-TIME SPREAD FOR {symbol}")
    print("="*50)
    print(f"Bid Price:         {tick.bid:.5f}")
    print(f"Ask Price:         {tick.ask:.5f}")
    print(f"Spread (USD):      {spread_usd:.5f}")
    print(f"Spread (Points):   {spread_points:.1f}")
    print(f"Point Size:        {info.point:.5f}")
    print(f"Digits:            {info.digits}")
    print(f"Last Tick Time:    {datetime.fromtimestamp(tick.time, timezone.utc)} (UTC)")
    print("="*50)
    
    # Let's get some recent tick statistics to see the average/min/max spread recently
    print("\nFetching last 1000 ticks for spread statistics...")
    start_time = datetime.now(timezone.utc) - timedelta(hours=2)
    ticks = mt5.copy_ticks_from(symbol, start_time, 1000, mt5.COPY_TICKS_ALL)
    if ticks is not None and len(ticks) > 0:
        spreads_usd = []
        spreads_points = []
        for t in ticks:
            s_usd = t['ask'] - t['bid']
            s_pts = s_usd / info.point
            spreads_usd.append(s_usd)
            spreads_points.append(s_pts)
            
        import numpy as np
        spreads_usd = np.array(spreads_usd)
        spreads_points = np.array(spreads_points)
        
        print("\n" + "="*50)
        print(f"       RECENT TICK SPREAD STATISTICS FOR {symbol}")
        print("="*50)
        print(f"Ticks Analyzed:             {len(spreads_usd)}")
        print(f"Average Spread:             {spreads_usd.mean():.5f} USD ({spreads_points.mean():.1f} points)")
        print(f"Median Spread (50th %):     {np.percentile(spreads_usd, 50):.5f} USD ({np.percentile(spreads_points, 50):.1f} points)")
        print(f"90th Percentile Spread:     {np.percentile(spreads_usd, 90):.5f} USD ({np.percentile(spreads_points, 90):.1f} points)")
        print(f"95th Percentile Spread:     {np.percentile(spreads_usd, 95):.5f} USD ({np.percentile(spreads_points, 95):.1f} points)")
        print(f"Minimum Spread:             {spreads_usd.min():.5f} USD ({spreads_points.min():.1f} points)")
        print(f"Maximum Spread:             {spreads_usd.max():.5f} USD ({spreads_points.max():.1f} points)")
        print("="*50)
    else:
        print("Could not retrieve historical ticks.")
        
    mt5.shutdown()

if __name__ == "__main__":
    main()
