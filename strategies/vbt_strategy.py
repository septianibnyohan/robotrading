import vectorbt as vbt
import pandas as pd
import numpy as np

class VBTsmaMomentum:
    """
    Re-implementation of SMA Momentum strategy using VectorBT's native indicators.
    Supports broadcasting for parameter optimization.
    """
    
    def __init__(self, fast_window=10, slow_window=50, rsi_window=14):
        self.fast_window = fast_window
        self.slow_window = slow_window
        self.rsi_window = rsi_window

    def run(self, close):
        """
        Calculates signals using VectorBT broadcasting.
        
        Args:
            close: pd.Series or pd.DataFrame of closing prices.
            
        Returns:
            entries: pd.DataFrame of entry signals.
            exits: pd.DataFrame of exit signals.
        """
        # Day 101: Native VectorBT Indicator runs
        # These automatically handle broadcasting if window is a list/array
        fast_ma = vbt.MA.run(close, window=self.fast_window)
        slow_ma = vbt.MA.run(close, window=self.slow_window)
        rsi = vbt.RSI.run(close, window=self.rsi_window)
        
        # Day 102: Vectorized Signal Logic
        # Long Entry: Fast SMA crosses above Slow SMA AND RSI < 70
        entries = fast_ma.ma_crossed_above(slow_ma) & (rsi.rsi < 70)
        
        # Long Exit: Fast SMA crosses below Slow SMA OR RSI > 85
        exits = fast_ma.ma_crossed_below(slow_ma) | (rsi.rsi > 85)
        
        # Short Entry: Fast SMA crosses below Slow SMA AND RSI > 30
        short_entries = fast_ma.ma_crossed_below(slow_ma) & (rsi.rsi > 30)
        
        # Short Exit: Fast SMA crosses above Slow SMA OR RSI < 15
        short_exits = fast_ma.ma_crossed_above(slow_ma) | (rsi.rsi < 15)
        
        return entries, exits, short_entries, short_exits

    def backtest(self, close, open_price=None, init_cash=10000, fees=0.0, slippage=0.0001, 
                 commission_per_lot=0.0, signal_delay=1, tp_stop=None, **kwargs):
        """
        Runs a full backtest using the calculated signals.
        
        Args:
            close: pd.Series or pd.DataFrame of closing prices (for decision).
            open_price: pd.Series or pd.DataFrame of opening prices (for execution).
            init_cash: Starting capital.
            fees: Percentage transaction fees.
            slippage: Slippage percentage.
            commission_per_lot: Fixed USD commission per lot.
            signal_delay: Delay between signal and execution (1 = next bar).
            tp_stop: Take profit stop percentage (e.g., 0.002 for 0.2%).
            **kwargs: Additional arguments for vbt.Portfolio.from_signals.
        """
        entries, exits, short_entries, short_exits = self.run(close)
        
        # Day 106: "Decide at Close, Execute at Next Open" Logic
        # Manually shift signals if signal_delay > 0
        if signal_delay > 0:
            entries = entries.vbt.fshift(signal_delay, fill_value=False)
            exits = exits.vbt.fshift(signal_delay, fill_value=False)
            short_entries = short_entries.vbt.fshift(signal_delay, fill_value=False)
            short_exits = short_exits.vbt.fshift(signal_delay, fill_value=False)

        # If open_price is not provided, we fall back to close
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

if __name__ == "__main__":
    # Example usage with broadcasting
    print("Example: Running with multiple fast_windows...")
    
    # Mock data
    price = pd.Series([100, 101, 102, 101, 100, 99, 101, 103, 105] * 20)
    
    strategy = VBTsmaMomentum(fast_window=[5, 10, 15], slow_window=20, rsi_window=14)
    entries, exits = strategy.run(price)
    
    print("Entry signals head:")
    print(entries.head())
    
    portfolio = strategy.backtest(price)
    print("\nTotal Returns per parameter combination:")
    print(portfolio.total_return())
