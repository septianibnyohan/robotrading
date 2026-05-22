import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import MetaTrader5 as mt5
from core.mt5_bridge import MT5Bridge
from monitoring.logger import setup_logging
from config.credentials import get_mt5_credentials
from data.storage import DataStorage
from data.harvester import DataHarvester

def main():
    logger = setup_logging()
    
    bridge = MT5Bridge()
    if not bridge.connect():
        logger.error("Failed to connect to MT5")
        return
        
    try:
        credentials = get_mt5_credentials()
        symbol = credentials.get('symbol', 'BTCUSD')
            
        timeframe = mt5.TIMEFRAME_M1
        
        storage = DataStorage()
        harvester = DataHarvester(storage)
        
        logger.info(f"Testing Harvester for {symbol}")
        
        logger.info("--- Test 1: Raw fetch_ohlcv ---")
        df_raw = harvester.fetch_ohlcv(symbol, timeframe, count=3)
        logger.info(f"Raw data:\n{df_raw}")
        
        logger.info("--- Test 2: Historical Harvest ---")
        harvester.harvest_historical(symbol, timeframe, count=10)
        df_hist = storage.load_rates(symbol, timeframe, limit=3)
        logger.info(f"Top 3 rows in storage after historical:\n{df_hist}")
        
        logger.info("--- Test 3: Immediate Incremental Sync ---")
        harvester.harvest_incremental(symbol, timeframe)
        df_inc = storage.load_rates(symbol, timeframe, limit=3)
        logger.info(f"Top 3 rows in storage after incremental sync:\n{df_inc}")
        
    finally:
        bridge.disconnect()

if __name__ == "__main__":
    main()
