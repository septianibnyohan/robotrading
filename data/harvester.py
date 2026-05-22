import MetaTrader5 as mt5
import pandas as pd
import logging
from datetime import datetime, timezone
from data.storage import DataStorage
from data.history_tracker import HistoryTracker
logger = logging.getLogger(__name__)

class DataHarvester:
    """
    Harvests historical and real-time market data from MT5.
    """
    def __init__(self, storage: DataStorage):
        self.storage = storage
        self.tracker = HistoryTracker()

    def fetch_ohlcv(self, symbol, timeframe, count=1000):
        """
        Fetches OHLCV data from MT5 terminal.
        """
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count)
        
        if rates is None:
            logger.warning(f"Failed to fetch rates for {symbol}: {mt5.last_error()}")
            return pd.DataFrame()
            
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s', utc=True)
        
        return df

    def harvest_historical(self, symbol, timeframe, count=10000):
        """
        Fetches and stores historical data, resuming from last fetched timestamp if available.
        """
        last_timestamp = self.tracker.get_last_timestamp(symbol, timeframe)
        
        if last_timestamp:
            logger.info(f"Resuming harvest for {symbol} on {timeframe} from timestamp {last_timestamp}...")
            now = int(datetime.now(timezone.utc).timestamp())
            rates = mt5.copy_rates_range(symbol, timeframe, int(last_timestamp), now)
        else:
            logger.info(f"Harvesting last {count} bars for {symbol} on {timeframe}...")
            rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count)
            
        if rates is None or len(rates) == 0:
            logger.warning(f"No new rates fetched for {symbol}: {mt5.last_error()}")
            return
            
        df = pd.DataFrame(rates)
        latest_time = int(df['time'].max()) # Get max timestamp before converting to datetime
        
        df['time'] = pd.to_datetime(df['time'], unit='s', utc=True)
        
        if not df.empty:
            self.storage.save_rates(symbol, timeframe, df)
            self.tracker.update_last_timestamp(symbol, timeframe, latest_time)
            logger.info(f"Harvested {len(df)} bars successfully. Tracker updated to {latest_time}.")
        else:
            logger.error("Harvesting failed.")

    def fetch_data_chunked(self, symbol, timeframe, chunk_days=10, default_lookback_days=30):
        """
        Requests data in manageable 'windows' and saves them block by block.
        Moves the 'start time' forward until it reaches the current moment.
        """
        last_timestamp = self.tracker.get_last_timestamp(symbol, timeframe)
        now = int(datetime.now(timezone.utc).timestamp())
        
        if last_timestamp:
            # Start from the next second to avoid duplicating the last bar
            current_start = int(last_timestamp) + 1
            logger.info(f"Resuming chunked harvest for {symbol} from timestamp {current_start}")
        else:
            current_start = now - (default_lookback_days * 86400)
            logger.info(f"Starting chunked harvest for {symbol} from {default_lookback_days} days ago")
            
        chunk_seconds = chunk_days * 86400
        total_fetched = 0
        
        while current_start < now:
            current_end = min(current_start + chunk_seconds, now)
            
            logger.info(f"Fetching chunk: {current_start} to {current_end}")
            rates = mt5.copy_rates_range(symbol, timeframe, current_start, current_end)
            
            if rates is not None and len(rates) > 0:
                df = pd.DataFrame(rates)
                latest_time = int(df['time'].max())
                
                df['time'] = pd.to_datetime(df['time'], unit='s', utc=True)
                self.storage.save_rates(symbol, timeframe, df)
                self.tracker.update_last_timestamp(symbol, timeframe, latest_time)
                
                bars_in_chunk = len(df)
                total_fetched += bars_in_chunk
                logger.info(f"Chunk saved: {bars_in_chunk} bars. Tracker updated to {latest_time}.")
            else:
                logger.warning(f"No data found for chunk {current_start} - {current_end}.")
                
            current_start = current_end + 1
            
        logger.info(f"Chunked harvest complete for {symbol} {timeframe}. Total new bars: {total_fetched}.")
        return total_fetched

    def get_latest_tick(self, symbol):
        """
        Fetches the most recent bid/ask tick.
        """
        tick = mt5.symbol_info_tick(symbol)
        if tick:
            return {
                "time": datetime.fromtimestamp(tick.time, tz=timezone.utc),
                "bid": tick.bid,
                "ask": tick.ask,
                "last": tick.last,
                "volume": tick.volume
            }
        return None

    def harvest_incremental(self, symbol, timeframe):
        """
        Polls for the most recently completed bar(s).
        This fetches a small number of recent bars and saves any that are newer than the last tracked timestamp.
        """
        last_timestamp = self.tracker.get_last_timestamp(symbol, timeframe)
        
        # Fetch last 5 bars to be safe (position 0 is current forming bar, 1 is last completed, etc.)
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, 5)
        
        if rates is None or len(rates) == 0:
            logger.warning(f"Incremental sync failed for {symbol}: {mt5.last_error()}")
            return
            
        df = pd.DataFrame(rates)
        
        # Exclude the current forming bar (the last row in chronological order)
        df = df.iloc[:-1]
        
        if last_timestamp:
            df = df[df['time'] > int(last_timestamp)]
            
        if not df.empty:
            latest_time = int(df['time'].max())
            df['time'] = pd.to_datetime(df['time'], unit='s', utc=True)
            
            self.storage.save_rates(symbol, timeframe, df)
            self.tracker.update_last_timestamp(symbol, timeframe, latest_time)
            logger.info(f"Incremental sync: Harvested {len(df)} new completed bars for {symbol}. Tracker updated to {latest_time}.")

