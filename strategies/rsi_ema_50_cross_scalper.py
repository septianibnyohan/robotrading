import pandas as pd
import numpy as np
import pandas_ta as ta
import logging
from strategies.base import TradingStrategy

logger = logging.getLogger(__name__)

class RsiEma50CrossScalperStrategy(TradingStrategy):
    """
    EMA + RSI(7) 50-Cross Scalper Strategy for XAUUSD.
    
    1. Trend filter: Fast EMA > Slow EMA (Long), Fast EMA < Slow EMA (Short)
    2. Momentum trigger: RSI(7) crossing 50
    3. Price confirmation: Close > Fast EMA (Long), Close < Fast EMA (Short)
    4. Volatility filter: ATR(14) > min_atr
    5. Flat market filter: |Fast EMA - Slow EMA| > 0.5 * ATR(14)
    """
    
    def __init__(self, fast_ema_period: int = 5, slow_ema_period: int = 13, 
                 rsi_period: int = 7, rsi_level: float = 50.0, min_atr: float = 0.8):
        self.fast_ema_period = fast_ema_period
        self.slow_ema_period = slow_ema_period
        self.rsi_period = rsi_period
        self.rsi_level = rsi_level
        self.min_atr = min_atr
        self.last_logged_time = None
        self.last_debug_time = None

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df

        df = df.sort_values('time').copy()
        
        # 1. EMAs using library
        df['fast_ema'] = ta.ema(df['close'], length=self.fast_ema_period)
        df['slow_ema'] = ta.ema(df['close'], length=self.slow_ema_period)
        
        # 2. RSI (Wilder's Smoothing - Standard MT5 RSI) using library
        df['rsi'] = ta.rsi(df['close'], length=self.rsi_period).fillna(50.0)
        # print("df :", df['rsi'])
        
        # 3. ATR (14) - SMA of True Range
        high_low = df['high'] - df['low']
        high_prev_close = (df['high'] - df['close'].shift(1)).abs()
        low_prev_close = (df['low'] - df['close'].shift(1)).abs()
        
        tr = pd.concat([high_low, high_prev_close, low_prev_close], axis=1).max(axis=1)
        df['atr'] = tr.rolling(window=14).mean()
        
        # For legacy logger compatibility (if needed)
        df['ema'] = df['fast_ema']
        df['sma_fast'] = df['fast_ema']
        df['sma_slow'] = df['slow_ema']
        
        return df

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Generates buy/sell signals based on closed candles (excludes current forming bar).
        """
        if df.empty or len(df) < max(self.slow_ema_period, 15):
            # Create columns so we don't crash
            df = df.copy()
            for col in ['fast_ema', 'slow_ema', 'rsi', 'atr', 'long_entry', 'short_entry', 'long_exit', 'short_exit']:
                df[col] = np.nan
            return df

        # We calculate indicators on the full dataset
        df = self.calculate_indicators(df)
        # print("df :", df.iloc[-1]['rsi'])
        
        # Add shift to prevent lookahead / repainting.
        # Since we evaluate "at candle close", a signal generated from candle index i
        # is executed on candle i+1.
        # So we can calculate triggers on index i and shift them forward by 1 bar,
        # OR we can just evaluate signals on the completed candles (excluding the forming bar)
        df['prev_rsi'] = df['rsi'].shift(1)
        
        # Common pre-filters on indicators
        # df['volatility_ok'] = df['atr'] > self.min_atr
        df['volatility_ok'] = True
        # df['ema_trend_ok'] = (df['fast_ema'] - df['slow_ema']).abs() > 0.5 * df['atr']
        df['ema_trend_ok'] = True
        
        # Long conditions
        df['long_entry'] = (
            df['volatility_ok'] &
            df['ema_trend_ok'] &
            (df['fast_ema'] > df['slow_ema']) &
            (df['prev_rsi'] <= self.rsi_level) & (df['rsi'] > self.rsi_level) &
            (df['close'] > df['fast_ema'])
        )
        
        # Short conditions
        df['short_entry'] = (
            df['volatility_ok'] &
            df['ema_trend_ok'] &
            (df['fast_ema'] < df['slow_ema']) &
            (df['prev_rsi'] >= self.rsi_level) & (df['rsi'] < self.rsi_level) &
            (df['close'] < df['fast_ema'])
        )
        
        # Scalping exits (time-based and SL/TP are handled at execution, 
        # but let's define technical exits just in case, e.g. reverse cross or trend change)
        df['long_exit'] = (df['fast_ema'] < df['slow_ema']) | (df['rsi'] < 40)
        df['short_exit'] = (df['fast_ema'] > df['slow_ema']) | (df['rsi'] > 60)
        
        # Convert signals to bool
        df['long_entry'] = df['long_entry'].fillna(False).astype(bool)
        df['short_entry'] = df['short_entry'].fillna(False).astype(bool)
        df['long_exit'] = df['long_exit'].fillna(False).astype(bool)
        df['short_exit'] = df['short_exit'].fillna(False).astype(bool)
        
        # Legacy/Simple signal column: 1 for Buy, -1 for Sell, 0 for None
        df['signal'] = 0
        df.loc[df['long_entry'], 'signal'] = 1
        df.loc[df['short_entry'], 'signal'] = -1
        
        # Real-time signal logging to console
        if not df.empty:
            last_row = df.iloc[-1]
            last_time = last_row.get('time')
            
            # 1. Debug logging of strategy conditions (once per completed candle)
            # if last_time != self.last_debug_time:
            ema_diff = last_row['fast_ema'] - last_row['slow_ema']
            trend_ok = last_row['ema_trend_ok']
            vol_ok = last_row['volatility_ok']

            long_criteria = {
                "volatility_ok": bool(vol_ok),
                "ema_trend_ok": bool(trend_ok),
                "fast_gt_slow": bool(last_row['fast_ema'] > last_row['slow_ema']),
                "rsi_cross_up": bool(last_row['prev_rsi'] <= self.rsi_level and last_row['rsi'] > self.rsi_level),
                "close_gt_fast": bool(last_row['close'] > last_row['fast_ema'])
            }

            short_criteria = {
                "volatility_ok": bool(vol_ok),
                "ema_trend_ok": bool(trend_ok),
                "fast_lt_slow": bool(last_row['fast_ema'] < last_row['slow_ema']),
                "rsi_cross_down": bool(last_row['prev_rsi'] >= self.rsi_level and last_row['rsi'] < self.rsi_level),
                "close_lt_fast": bool(last_row['close'] < last_row['fast_ema'])
            }

            logger.info(
                f"[STRATEGY DEBUG] Candle: {last_time} | Close: {last_row['close']:.2f} | "
                f"Fast EMA: {last_row['fast_ema']:.2f} | Slow EMA: {last_row['slow_ema']:.2f} (diff: {ema_diff:.2f}, threshold: {0.5*last_row['atr']:.2f}) | "
                f"RSI(7): {last_row['rsi']:.2f} (prev: {last_row['prev_rsi']:.2f}) | ATR(14): {last_row['atr']:.2f} | "
                f"Long Criteria: {long_criteria} | "
                f"Short Criteria: {short_criteria}\n"
                f"--- DataFrame Tail ---\n"
                f"{df[['time', 'close', 'fast_ema', 'slow_ema', 'rsi', 'atr', 'signal']].tail(5).to_string()}\n"
                f"----------------------"
            )
            self.last_debug_time = last_time
            
            # 2. Informational entry logs
            if last_time != self.last_logged_time:
                if last_row['long_entry']:
                    logger.info(
                        f"[STRATEGY] LONG entry signal generated on completed candle {last_time} | "
                        f"Close: {last_row['close']:.2f} | Fast EMA: {last_row['fast_ema']:.2f} | Slow EMA: {last_row['slow_ema']:.2f} | "
                        f"RSI(7): {last_row['rsi']:.2f} (prev: {last_row['prev_rsi']:.2f}) | ATR(14): {last_row['atr']:.2f}"
                    )
                    self.last_logged_time = last_time
                elif last_row['short_entry']:
                    logger.info(
                        f"[STRATEGY] SHORT entry signal generated on completed candle {last_time} | "
                        f"Close: {last_row['close']:.2f} | Fast EMA: {last_row['fast_ema']:.2f} | Slow EMA: {last_row['slow_ema']:.2f} | "
                        f"RSI(7): {last_row['rsi']:.2f} (prev: {last_row['prev_rsi']:.2f}) | ATR(14): {last_row['atr']:.2f}"
                    )
                    self.last_logged_time = last_time
        
        return df
