import sqlite3
import os
import logging
from datetime import datetime, timezone
import pandas as pd
import MetaTrader5 as mt5

logger = logging.getLogger(__name__)

class TradeRsiLogger:
    def __init__(self, db_path="data/database/market_data.sqlite"):
        self.db_path = db_path
        self._ensure_table_exists()

    def _ensure_table_exists(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS trade_rsi_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    ticket INTEGER,
                    action TEXT,
                    symbol TEXT,
                    price REAL,
                    volume REAL,
                    rsi_m1 REAL,
                    rsi_m5 REAL,
                    rsi_m15 REAL,
                    rsi_30 REAL,
                    rsi_h1 REAL,
                    rsi_h4 REAL,
                    rsi_d1 REAL,
                    rsi_w1 REAL
                )
            """)
            conn.commit()
        except Exception as e:
            logger.error(f"Error creating trade_rsi_log table: {e}")
        finally:
            conn.close()

    def _calculate_rsi(self, symbol, timeframe, period=14):
        """
        Fetches the last 150 rates for the specified symbol and timeframe,
        and calculates the standard 14-period RSI (Wilder's smoothing).
        Returns the latest RSI value (float) or 50.0 on failure.
        """
        try:
            rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, 150)
            if rates is None or len(rates) < period + 1:
                logger.warning(
                    f"Could not fetch sufficient rates for {symbol} on timeframe {timeframe} "
                    f"(got {len(rates) if rates is not None else 'None'}). Fallback to 50.0."
                )
                return 50.0
            
            df = pd.DataFrame(rates)
            delta = df['close'].diff()
            gain = delta.where(delta > 0, 0.0)
            loss = -delta.where(delta < 0, 0.0)
            
            avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
            avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()
            
            rs = avg_gain / (avg_loss + 1e-10)
            rsi = 100 - (100 / (1 + rs))
            
            val = rsi.iloc[-1]
            if pd.isna(val):
                return 50.0
            return float(val)
        except Exception as e:
            logger.error(f"Error calculating RSI for {symbol} {timeframe}: {e}")
            return 50.0

    def log_trade(self, ticket, action, symbol, price, volume):
        """
        Fetches multi-timeframe RSI values and logs the trade/close details to SQLite.
        """
        timeframes = {
            'rsi_m1': mt5.TIMEFRAME_M1,
            'rsi_m5': mt5.TIMEFRAME_M5,
            'rsi_m15': mt5.TIMEFRAME_M15,
            'rsi_30': mt5.TIMEFRAME_M30,
            'rsi_h1': mt5.TIMEFRAME_H1,
            'rsi_h4': mt5.TIMEFRAME_H4,
            'rsi_d1': mt5.TIMEFRAME_D1,
            'rsi_w1': mt5.TIMEFRAME_W1
        }
        
        rsi_values = {}
        for rsi_name, tf_const in timeframes.items():
            rsi_values[rsi_name] = self._calculate_rsi(symbol, tf_const)
            
        timestamp = datetime.now(timezone.utc).isoformat()
        
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO trade_rsi_log (
                    timestamp, ticket, action, symbol, price, volume,
                    rsi_m1, rsi_m5, rsi_m15, rsi_30, rsi_h1, rsi_h4, rsi_d1, rsi_w1
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                timestamp,
                int(ticket) if ticket is not None else None,
                action,
                symbol,
                float(price) if price is not None else 0.0,
                float(volume) if volume is not None else 0.0,
                rsi_values['rsi_m1'],
                rsi_values['rsi_m5'],
                rsi_values['rsi_m15'],
                rsi_values['rsi_30'],
                rsi_values['rsi_h1'],
                rsi_values['rsi_h4'],
                rsi_values['rsi_d1'],
                rsi_values['rsi_w1']
            ))
            conn.commit()
            logger.info(f"Logged trade to database: {action} ticket {ticket} for {symbol} with MTF RSIs.")
        except Exception as e:
            logger.error(f"Error inserting trade log to database: {e}")
        finally:
            conn.close()
