import pandas as pd
import numpy as np
from strategies.base import TradingStrategy

class SMAMomentumStrategy(TradingStrategy):
    """
    BTCUSD Trend-Following + Momentum Strategy (SMA 10/50 + RSI 14).
    
    This strategy identifies bullish trend entries using a Simple Moving Average (SMA) 
    crossover while filtering for momentum using the Relative Strength Index (RSI).
    It is designed to be mathematically rigorous, using vectorized operations and 
    Wilder's smoothing for RSI.

    Attributes:
        fast_window (int): Period for the fast SMA.
        slow_window (int): Period for the slow SMA.
        rsi_window (int): Period for the RSI calculation.
    """
    
    def __init__(self, fast_window: int = 10, slow_window: int = 50, rsi_window: int = 14):
        """
        Initializes the strategy with configurable windows.
        
        Args:
            fast_window: The lookback period for the fast SMA.
            slow_window: The lookback period for the slow SMA.
            rsi_window: The lookback period for the RSI.
        """
        self.fast_window = fast_window
        self.slow_window = slow_window
        self.rsi_window = rsi_window

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculates SMAs and RSI with vectorized precision.
        
        Args:
            df: DataFrame containing at least 'time' and 'close' columns.
            
        Returns:
            DataFrame with 'sma_fast', 'sma_slow', and 'rsi' columns added.
        """
        if df.empty:
            return df

        df = df.sort_values('time').copy()
        
        # Day 94: Vectorized SMA with min_periods
        df['sma_fast'] = df['close'].rolling(
            window=self.fast_window, min_periods=self.fast_window
        ).mean()
        df['sma_slow'] = df['close'].rolling(
            window=self.slow_window, min_periods=self.slow_window
        ).mean()
        
        # Day 95: RSI Logic using Wilder's Smoothing (EWM)
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0))
        loss = (-delta.where(delta < 0, 0))
        
        # alpha = 1/window is the standard for Wilder's Smoothing
        avg_gain = gain.ewm(
            alpha=1/self.rsi_window, adjust=False, min_periods=self.rsi_window
        ).mean()
        avg_loss = loss.ewm(
            alpha=1/self.rsi_window, adjust=False, min_periods=self.rsi_window
        ).mean()
        
        # Handle division by zero
        rs = np.where(avg_loss != 0, avg_gain / avg_loss, 0)
        df['rsi'] = 100 - (100 / (1 + rs))
        
        return df

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Generates Entry/Exit signals for both Long and Short positions 
        with lookahead prevention.
        
        Logic:
            Long Entry: Fast SMA crosses above Slow SMA AND RSI < 70
            Long Exit: Fast SMA crosses below Slow SMA OR RSI > 85
            Short Entry: Fast SMA crosses below Slow SMA AND RSI > 30
            Short Exit: Fast SMA crosses above Slow SMA OR RSI < 15
        
        Args:
            df: DataFrame containing price and indicator data.
            
        Returns:
            DataFrame with 'long_entry', 'long_exit', 'short_entry', 'short_exit' boolean columns.
        """
        if df.empty:
            return df

        df = self.calculate_indicators(df)
        
        # Day 97: Crossover Detection with .shift(1) to prevent lookahead bias
        df['prev_sma_fast'] = df['sma_fast'].shift(1)
        df['prev_sma_slow'] = df['sma_slow'].shift(1)
        
        # Crossover Above Trigger
        df['bullish_trigger'] = (df['sma_fast'] > df['sma_slow']) & \
                                (df['prev_sma_fast'] <= df['prev_sma_slow'])
        
        # Crossover Below Trigger
        df['bearish_trigger'] = (df['sma_fast'] < df['sma_slow']) & \
                                (df['prev_sma_fast'] >= df['prev_sma_slow'])
        
        # Define 4 distinct signal columns as booleans
        df['long_entry'] = df['bullish_trigger'] & (df['rsi'] < 70)
        df['long_exit'] = df['bearish_trigger'] | (df['rsi'] > 85)
        
        df['short_entry'] = df['bearish_trigger'] & (df['rsi'] > 30)
        df['short_exit'] = df['bullish_trigger'] | (df['rsi'] < 15)
        
        # Compatibility/Legacy 'signal' column (optional, but good for simple plotting)
        # 1 for Long Entry, -1 for Short Entry, 0 for Flat/Exit
        df['signal'] = 0
        df.loc[df['long_entry'], 'signal'] = 1
        df.loc[df['short_entry'], 'signal'] = -1
        
        return df
