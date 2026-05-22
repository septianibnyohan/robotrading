import MetaTrader5 as mt5
import sys
import os
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data.harvester import DataHarvester
from data.storage import DataStorage
from monitoring.logger import setup_logging

def main():
    logger = setup_logging()
    load_dotenv()

    if not mt5.initialize():
        logger.error(f"MT5 initialization failed: {mt5.last_error()}")
        return

    storage = DataStorage()
    harvester = DataHarvester(storage)

    symbols = ["XAUUSD", "USTEC"]
    timeframe = mt5.TIMEFRAME_M1
    
    # Fetch last 10,000 bars for each (approx 1 week)
    for symbol in symbols:
        logger.info(f"Harvesting data for {symbol}...")
        harvester.harvest_historical(symbol, timeframe, count=10000)

    mt5.shutdown()
    logger.info("Data preparation complete.")

if __name__ == "__main__":
    main()
