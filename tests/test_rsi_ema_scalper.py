import pandas as pd
import numpy as np
import pytest
from strategies.rsi_ema_scalper import RSIEmaScalperStrategy

def test_generate_signals_columns():
    """Verify that generate_signals returns a DataFrame with all required signal columns."""
    strategy = RSIEmaScalperStrategy(ema_window=10, rsi_window=5, rsi_extreme=30)
    
    # Create 20 rows of dummy data with a 'time' column
    df = pd.DataFrame({
        'time': pd.date_range('2023-01-01', periods=20, freq='1min'),
        'open': np.random.randn(20) + 100,
        'high': np.random.randn(20) + 101,
        'low': np.random.randn(20) + 99,
        'close': np.random.randn(20) + 100,
        'tick_volume': [100] * 20
    })
    
    result = strategy.generate_signals(df)
    
    expected_cols = ['rsi', 'ema', 'prev_rsi', 'long_entry', 'short_entry', 'long_exit', 'short_exit']
    for col in expected_cols:
        assert col in result.columns, f"Missing column: {col}"
    
    assert len(result) == 20

def test_rsi_crossover_logic():
    """Verify that RSI crossover signals trigger correctly on the last bar."""
    # We use a very small window to make RSI hypersensitive for testing
    strategy = RSIEmaScalperStrategy(ema_window=200, rsi_window=2, rsi_extreme=20)
    
    # Sequence of closes designed to force an RSI dip and spike
    closes = [100, 95, 90, 85, 80, 75, 70, 65, 60, 55, 50, 100] # Spike from 50 to 100
    df = pd.DataFrame({
        'time': pd.date_range('2023-01-01', periods=len(closes), freq='1min'),
        'open': closes,
        'high': closes,
        'low': closes,
        'close': closes,
        'tick_volume': [100] * len(closes)
    })
    
    result = strategy.generate_signals(df)
    
    last_rsi = result['rsi'].iloc[-1]
    prev_rsi = result['rsi'].iloc[-2]
    
    print(f"DEBUG TEST: Prev RSI={prev_rsi:.2f}, Current RSI={last_rsi:.2f}")
    
    # Long Entry: RSI crosses above 30
    if last_rsi > 20 and prev_rsi <= 20:
        assert result['long_entry'].iloc[-1] == True
    
    # Long Exit: RSI crosses above 50
    if last_rsi > 50 and prev_rsi <= 50:
        assert result['long_exit'].iloc[-1] == True

if __name__ == "__main__":
    pytest.main([__file__])
