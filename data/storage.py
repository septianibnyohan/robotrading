import sqlite3
import pandas as pd
import os
import logging

logger = logging.getLogger(__name__)

class DataStorage:
    """
    Manages local SQLite storage for historical market data.
    """
    def __init__(self, db_path="data/database/market_data.sqlite"):
        self.db_path = db_path
        self._ensure_db_dir()

    def _ensure_db_dir(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

    def save_rates(self, symbol, timeframe, rates_df):
        """
        Saves OHLCV data to the database using a merge-and-purge strategy
        to prevent duplicate timestamps.
        """
        if rates_df.empty:
            return
            
        # 1. Purge intra-chunk duplicates using Pandas
        rates_df = rates_df.drop_duplicates(subset=['time'])
            
        table_name = f"{symbol}_{timeframe}"
        temp_table = f"temp_{table_name}"
        
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            
            # Check if main table exists
            cursor.execute("SELECT count(name) FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
            if cursor.fetchone()[0] == 0:
                # Table doesn't exist, create it by writing directly
                rates_df.to_sql(table_name, conn, if_exists='replace', index=False)
                # Add unique index for future inserts
                cursor.execute(f"CREATE UNIQUE INDEX idx_{table_name}_time ON {table_name} (time)")
                conn.commit()
                logger.debug(f"Created new table {table_name} and saved {len(rates_df)} rows.")
                return

            # Ensure unique index exists (in case the table was created before this update)
            cursor.execute(f"CREATE UNIQUE INDEX IF NOT EXISTS idx_{table_name}_time ON {table_name} (time)")
            
            # 2. Merge and Purge against database using SQL
            # Write to temp table
            rates_df.to_sql(temp_table, conn, if_exists='replace', index=False)
            
            # Insert or ignore into main table
            cursor.execute(f"INSERT OR IGNORE INTO {table_name} SELECT * FROM {temp_table}")
            inserted = cursor.rowcount
            
            # Clean up
            cursor.execute(f"DROP TABLE {temp_table}")
            conn.commit()
            
            logger.info(f"Merge and purge for {table_name}: Inserted {inserted} new rows (out of {len(rates_df)} fetched).")
        except Exception as e:
            logger.error(f"Error saving data to SQLite: {e}")
        finally:
            conn.close()

    def load_rates(self, symbol, timeframe, limit=1000):
        """
        Loads OHLCV data from the database.
        """
        table_name = f"{symbol}_{timeframe}"
        conn = sqlite3.connect(self.db_path)
        try:
            query = f"SELECT * FROM {table_name} ORDER BY time DESC LIMIT {limit}"
            return pd.read_sql(query, conn)
        except Exception as e:
            logger.error(f"Error loading data from SQLite: {e}")
            return pd.DataFrame()
        finally:
            conn.close()
