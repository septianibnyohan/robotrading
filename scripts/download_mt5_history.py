import sys
import os
import sqlite3
import pandas as pd
from datetime import datetime, timezone, timedelta
import logging

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import btc_config
from data.storage import DataStorage
from monitoring.logger import setup_logging

logger = setup_logging()

def download_symbol_history(symbol, years=2, chunk_size=50000):
    """Downloads historical M1 data from MT5 in chunks and saves to SQLite."""
    import MetaTrader5 as mt5
    
    logger.info(f"Connecting to MetaTrader 5 to download {symbol} history...")
    if not mt5.initialize():
        logger.error(f"Failed to initialize MT5: {mt5.last_error()}")
        return False
        
    # Check maxbars option
    terminal_info = mt5.terminal_info()
    max_bars = getattr(terminal_info, "maxbars", 100000)
    logger.info(f"Terminal Max Bars in Chart setting: {max_bars}")
    if max_bars < 1000000:
        logger.warning("="*70)
        logger.warning("WARNING: Your MetaTrader 5 terminal 'Max bars in chart' option is set low.")
        logger.warning("To download 2 years of history, please do the following in MT5:")
        logger.warning("  1. Go to Tools -> Options -> Charts")
        logger.warning("  2. Set 'Max bars in chart' to 'Unlimited' or at least '1000000'")
        logger.warning("  3. Restart the MT5 terminal.")
        logger.warning("="*70)
        
    mt5.symbol_select(symbol, True)
    
    # Calculate estimated M1 bars for target years
    # 2 years = 2 * 365 * 1440 = ~1,051,200 bars
    target_bars = int(years * 365 * 1440)
    logger.info(f"Targeting {years} year(s) of history (~{target_bars:,} M1 bars) for {symbol}...")
    
    storage = DataStorage()
    
    total_downloaded = 0
    start_pos = 0
    
    dfs = []
    from btc_indicators import rates_to_df
    
    while total_downloaded < target_bars:
        # Determine size to request
        req_size = min(chunk_size, target_bars - total_downloaded)
        logger.info(f"Requesting chunk of {req_size:,} bars starting at index {start_pos:,}...")
        
        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M1, start_pos, req_size)
        if rates is None or len(rates) == 0:
            logger.info("No more rates returned from MetaTrader 5. Reached end of available history.")
            break
            
        dfs.append(rates_to_df(rates))
        downloaded = len(rates)
        total_downloaded += downloaded
        start_pos += downloaded
        
        # If we got fewer bars than requested, we hit the broker limit
        if downloaded < req_size:
            logger.info(f"Broker returned fewer bars than requested. Reached end of history on broker server.")
            break
            
    mt5.shutdown()
    
    if not dfs:
        logger.error("No rates downloaded.")
        return False
        
    # Concatenate and convert to DataFrame
    df = pd.concat(dfs, ignore_index=True)
    
    # Sort and remove duplicates
    df = df.drop_duplicates(subset=['time']).sort_values('time').reset_index(drop=True)
    
    logger.info(f"Downloaded {len(df):,} unique M1 bars total.")
    if len(df) > 0:
        logger.info(f"Date range: {df['time'].iloc[0]} to {df['time'].iloc[-1]}")
        
    # Save directly to SQLite using DataStorage helper
    logger.info("Saving history to local SQLite database...")
    storage.save_rates(symbol, 1, df)
    logger.info(f"Successfully saved {len(df):,} rates to SQLite database table '{symbol}_1'.")
    return True

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Download large market history from MT5 to local SQLite database.")
    parser.add_argument("--symbol", type=str, default="BTCUSDc", help="Symbol to download")
    parser.add_argument("--years", type=float, default=2.0, help="Number of years of history to download")
    args = parser.parse_args()
    
    download_symbol_history(args.symbol, years=args.years)
