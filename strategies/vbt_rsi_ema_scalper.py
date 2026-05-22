import vectorbt as vbt
import pandas as pd
import numpy as np

class VBTrsiEmaScalper:
    """
    VectorBT implementation of the RSI-EMA Scalper Strategy.
    """
    
    def __init__(self, ema_window=200, rsi_window=5, rsi_extreme=20):
        self.ema_window = ema_window
        self.rsi_window = rsi_window
        self.rsi_extreme = rsi_extreme
        self.short_rsi_extreme = 100 - rsi_extreme

    def run(self, close):
        """
        Calculates signals using VectorBT broadcasting.
        """
        # EMA using ewm=True to signify Exponential Moving Average
        ema = vbt.MA.run(close, window=self.ema_window, ewm=True)
        rsi = vbt.RSI.run(close, window=self.rsi_window)
        
        bull_trend = close > ema.ma
        bear_trend = close < ema.ma
        
        # Entries: Dip buying in Bull Trend, Spike selling in Bear Trend
        entries = bull_trend & rsi.rsi_crossed_above(self.rsi_extreme)
        short_entries = bear_trend & rsi.rsi_crossed_below(self.short_rsi_extreme)
        
        # Exits: Mean Reversion to 50
        exits = rsi.rsi_crossed_above(50)
        short_exits = rsi.rsi_crossed_below(50)
        
        return entries, exits, short_entries, short_exits

    def backtest(self, close, open_price=None, init_cash=10000, fees=0.0, slippage=0.0001, 
                 commission_per_lot=0.0, signal_delay=1, tp_stop=None, **kwargs):
        """
        Runs a full backtest using the calculated signals.
        """
        entries, exits, short_entries, short_exits = self.run(close)
        
        # Delay execution by 1 bar to prevent lookahead bias
        if signal_delay > 0:
            entries = entries.vbt.fshift(signal_delay, fill_value=False)
            exits = exits.vbt.fshift(signal_delay, fill_value=False)
            short_entries = short_entries.vbt.fshift(signal_delay, fill_value=False)
            short_exits = short_exits.vbt.fshift(signal_delay, fill_value=False)

        exec_price = open_price if open_price is not None else close

        if commission_per_lot > 0:
            dynamic_fees = (commission_per_lot / exec_price) + fees
        else:
            dynamic_fees = fees

        portfolio = vbt.Portfolio.from_signals(
            close, 
            entries=entries, 
            exits=exits, 
            short_entries=short_entries,
            short_exits=short_exits,
            price=exec_price,
            init_cash=init_cash, 
            fees=dynamic_fees,
            slippage=slippage,
            tp_stop=tp_stop,
            **kwargs
        )

        return portfolio
