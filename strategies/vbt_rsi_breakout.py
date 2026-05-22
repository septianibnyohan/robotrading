import vectorbt as vbt
import pandas as pd
import numpy as np

class VBTrsiBreakout:
    """
    VectorBT implementation of the RSI Breakout Strategy.
    """
    
    def __init__(self, rsi_window=14, 
                 long_entry=30, long_tp=35, long_sl=28,
                 short_entry=70, short_tp=65, short_sl=72):
        self.rsi_window = rsi_window
        self.long_entry = long_entry
        self.long_tp = long_tp
        self.long_sl = long_sl
        self.short_entry = short_entry
        self.short_tp = short_tp
        self.short_sl = short_sl

    def run(self, close):
        """
        Calculates signals using VectorBT broadcasting.
        """
        rsi = vbt.RSI.run(close, window=self.rsi_window)
        
        # Long Entry
        entries = rsi.rsi_crossed_above(self.long_entry)
        
        # Long Exit: TP or SL
        exits = rsi.rsi_crossed_above(self.long_tp) | rsi.rsi_crossed_below(self.long_sl)
        
        # Short Entry
        short_entries = rsi.rsi_crossed_below(self.short_entry)
        
        # Short Exit: TP or SL
        short_exits = rsi.rsi_crossed_below(self.short_tp) | rsi.rsi_crossed_above(self.short_sl)

        
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
