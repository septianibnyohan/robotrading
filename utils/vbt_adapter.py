import pandas as pd
import vectorbt as vbt
import logging
from data.storage import DataStorage

logger = logging.getLogger(__name__)

class VBTDataLoader:
    """
    Adapter to bridge project data storage (SQLite/Parquet) with VectorBT.
    """
    def __init__(self, db_path="data/database/market_data.sqlite"):
        self.storage = DataStorage(db_path=db_path)

    def from_sqlite(self, symbol: str, timeframe: str, limit: int = 100000) -> vbt.Data:
        """
        Loads data from SQLite and converts it to a VectorBT Data object.
        
        Args:
            symbol: The trading symbol (e.g., 'BTCUSD').
            timeframe: The timeframe string (e.g., 'H1').
            limit: Maximum number of rows to load.
            
        Returns:
            vbt.Data object with correctly indexed OHLCV data.
        """
        logger.info(f"Loading {symbol} {timeframe} from SQLite into VectorBT...")
        
        # Load raw dataframe from storage
        df = self.storage.load_rates(symbol, timeframe, limit=limit)
        
        if df.empty:
            logger.warning(f"No data found for {symbol} {timeframe} in SQLite.")
            return None

        # Day 100: Standardizing index for VectorBT
        # VectorBT requires a DatetimeIndex for most time-series operations.
        if 'time' in df.columns:
            # Automatic parsing of datetime strings or timestamps
            df['time'] = pd.to_datetime(df['time'], utc=True)
            df.set_index('time', inplace=True)
        
        # Ensure OHLCV columns are present and correctly named
        # Expected: open, high, low, close, tick_volume (or volume)
        df.sort_index(inplace=True)
        
        # Wrap in VectorBT Data container
        # Using a dictionary to specify the symbol name clearly
        # Explicitly passing download_kwargs to satisfy VectorBT 1.0.0 requirements
        return vbt.Data.from_data({symbol: df}, download_kwargs={})

    def from_parquet(self, file_path: str, symbol: str = "Unknown") -> vbt.Data:
        """
        Loads data from a Parquet file and converts it to a VectorBT Data object.
        
        Args:
            file_path: Path to the .parquet file.
            
        Returns:
            vbt.Data object.
        """
        logger.info(f"Loading data from Parquet: {file_path}")
        
        df = pd.read_parquet(file_path)
        
        if 'time' in df.columns:
            df['time'] = pd.to_datetime(df['time'], utc=True)
            df.set_index('time', inplace=True)
            
        df.sort_index(inplace=True)
        
        return vbt.Data.from_data({symbol: df}, download_kwargs={})

if __name__ == "__main__":
    # Quick sanity check
    logging.basicConfig(level=logging.INFO)
    loader = VBTDataLoader()
    # Try to load BTCUSD H1 if it exists
    data = loader.from_sqlite("BTCUSD", "H1", limit=100)
    if data:
        print("Successfully loaded data into VectorBT:")
        print(data.get())
    else:
        print("No data available for sanity check.")
