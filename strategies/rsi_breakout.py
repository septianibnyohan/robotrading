import pandas as pd
import numpy as np
from strategies.base import TradingStrategy

class RSIBreakoutStrategy(TradingStrategy):
    """
    BTCUSD RSI Breakout Scalping Strategy.
    
    This strategy executes rapid mean-reversion trades based on RSI breaking out 
    from extreme zones, with tight profit targets and stop losses.
    """
    
    def __init__(self, rsi_window: int = 14):
        self.rsi_window = rsi_window

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculates RSI with vectorized precision.
        """
        if df.empty:
            return df

        df = df.sort_values('time').copy()
        
        # RSI Logic using Wilder's Smoothing (EWM)
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0))
        loss = (-delta.where(delta < 0, 0))
        
        avg_gain = gain.ewm(
            alpha=1/self.rsi_window, adjust=False, min_periods=self.rsi_window
        ).mean()
        avg_loss = loss.ewm(
            alpha=1/self.rsi_window, adjust=False, min_periods=self.rsi_window
        ).mean()
        
        # Handle division by zero
        rs = np.where(avg_loss != 0, avg_gain / avg_loss, 0)
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # Keep empty columns for main.py compatibility (it expects sma_fast and sma_slow)
        df['sma_fast'] = 0.0
        df['sma_slow'] = 0.0
        
        return df

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Generates Entry/Exit signals for Long and Short positions based on RSI boundaries.
        """
        if df.empty:
            return df

        df = self.calculate_indicators(df)
        
        # Shift RSI to prevent lookahead bias in crossover detection
        df['prev_rsi'] = df['rsi'].shift(1)
        
        # Helper lambda for crossovers
        crosses_above = lambda col, val: (df[col] > val) & (df['prev_' + col] <= val)
        crosses_below = lambda col, val: (df[col] < val) & (df['prev_' + col] >= val)
        
        # Define 4 distinct signal columns as booleans
        # Long Entry: RSI crosses above 30
        df['long_entry'] = crosses_above('rsi', 30)
        # Long Exit: TP (crosses above 35) or SL (crosses below 28)
        df['long_exit'] = crosses_above('rsi', 35) #| crosses_below('rsi', 28)
        
        # Short Entry: RSI crosses below 70
        df['short_entry'] = crosses_below('rsi', 70)
        # Short Exit: TP (crosses below 65) or SL (crosses above 72)
        df['short_exit'] = crosses_below('rsi', 65) #| crosses_above('rsi', 72)
        
        # Legacy signal column for basic visualization
        df['signal'] = 0
        df.loc[df['long_entry'], 'signal'] = 1
        df.loc[df['short_entry'], 'signal'] = -1
        
        return df
