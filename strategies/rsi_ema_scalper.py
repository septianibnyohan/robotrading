import pandas as pd
import numpy as np
from strategies.base import TradingStrategy

class RSIEmaScalperStrategy(TradingStrategy):
    """
    BTCUSD RSI-EMA Scalper Strategy.
    
    Uses an EMA 200 to establish the macro trend, and a fast RSI (e.g. 5) 
    to buy micro-pullbacks (dips in an uptrend, spikes in a downtrend).
    """
    
    def __init__(self, ema_window: int = 200, rsi_window: int = 5, rsi_extreme: int = 20):
        self.ema_window = ema_window
        self.rsi_window = rsi_window
        self.rsi_extreme = rsi_extreme
        self.short_rsi_extreme = 100 - rsi_extreme

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df

        df = df.sort_values('time').copy()
        
        # 1. EMA Trend Filter
        df['ema'] = df['close'].ewm(span=self.ema_window, adjust=False).mean()
        
        # 2. Fast RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0))
        loss = (-delta.where(delta < 0, 0))
        
        avg_gain = gain.ewm(alpha=1/self.rsi_window, adjust=False, min_periods=self.rsi_window).mean()
        avg_loss = loss.ewm(alpha=1/self.rsi_window, adjust=False, min_periods=self.rsi_window).mean()
        
        rs = np.where(avg_loss != 0, avg_gain / avg_loss, 0)
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # Aliases for main.py legacy logger compatibility
        df['sma_fast'] = df['ema']
        df['sma_slow'] = df['ema']
        
        return df

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Generates Entry/Exit signals based on Pullbacks in the direction of the EMA trend.
        """
        if df.empty:
            return df

        df = self.calculate_indicators(df)
        
        df['prev_rsi'] = df['rsi'].shift(1)
        
        # Trend Conditions
        bull_trend = df['close'] > df['ema']
        bear_trend = df['close'] < df['ema']
        
        # RSI Crossovers
        def crosses_above(col, val):
            series = (df[col] > val) & (df['prev_' + col] <= val)
            print(f"RSI Check [Above] | Current: {df[col].iloc[-1]:.2f} | Prev: {df['prev_' + col].iloc[-1]:.2f} | Threshold: {val} | Signal: {series.iloc[-1]}")
            return series
            
        def crosses_below(col, val):
            series = (df[col] < val) & (df['prev_' + col] >= val)
            print(f"RSI Check [Below] | Current: {df[col].iloc[-1]:.2f} | Prev: {df['prev_' + col].iloc[-1]:.2f} | Threshold: {val} | Signal: {series.iloc[-1]}")
            return series
        
        # Long Entry: Bull trend & RSI crosses above the oversold extreme (e.g. 20)
        df['long_entry'] = crosses_above('rsi', self.rsi_extreme) #bull_trend & crosses_above('rsi', self.rsi_extreme)
        
        # Long Exit: RSI crosses above 50 (Mean reversion)
        df['long_exit'] = crosses_above('rsi', 50)
        
        # Short Entry: Bear trend & RSI crosses below the overbought extreme (e.g. 80)
        df['short_entry'] = crosses_below('rsi', self.short_rsi_extreme) #bear_trend & crosses_below('rsi', self.short_rsi_extreme)
        
        # Short Exit: RSI crosses below 50 (Mean reversion)
        df['short_exit'] = crosses_below('rsi', 50)
        
        return df
