import sys
import os
import pandas as pd
import numpy as np
import pytest
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from strategies.rsi_ema_50_cross_scalper import RsiEma50CrossScalperStrategy

def test_indicators_columns():
    """Verify that calculate_indicators adds all expected columns."""
    strategy = RsiEma50CrossScalperStrategy(fast_ema_period=5, slow_ema_period=13, rsi_period=7, min_atr=0.8)
    
    # 30 bars of dummy data
    closes = np.random.randn(30) + 2000.0
    highs = closes + 1.5
    lows = closes - 1.5
    opens = closes - 0.1
    
    df = pd.DataFrame({
        'time': pd.date_range('2026-01-01', periods=30, freq='1min'),
        'open': opens,
        'high': highs,
        'low': lows,
        'close': closes,
        'tick_volume': [100] * 30
    })
    
    result = strategy.calculate_indicators(df)
    
    # Check that indicator columns exist
    for col in ['fast_ema', 'slow_ema', 'rsi', 'atr']:
        assert col in result.columns, f"Indicator column {col} is missing"
        
    assert len(result) == 30

def test_long_entry_trigger():
    """Verify that a long entry is triggered when all conditions align."""
    strategy = RsiEma50CrossScalperStrategy(
        fast_ema_period=3, 
        slow_ema_period=6, 
        rsi_period=2, 
        rsi_level=50.0, 
        min_atr=0.1
    )
    
    # Construct a sequence of prices to force conditions:
    # 1. fast_ema > slow_ema (uptrend)
    # 2. RSI crosses above 50
    # 3. close > fast_ema
    # 4. atr > min_atr
    # 5. fast_ema - slow_ema > 0.5 * atr
    
    # Open, High, Low, Close
    # Bar 0-5: stable low price
    # Bar 6: start moving up
    # Bar 7: cross RSI above 50 and make close > fast_ema
    closes = [100.0] * 15 + [100.0, 100.0, 100.0, 100.0, 100.0, 108.0, 110.0, 112.0, 114.0, 116.0]
    highs =  [100.5] * 15 + [100.5, 100.5, 100.5, 100.5, 100.5, 109.0, 111.0, 113.0, 115.0, 117.0]
    lows =   [ 99.5] * 15 + [ 99.5,  99.5,  99.5,  99.5,  99.5, 107.0, 109.0, 111.0, 113.0, 115.0]
    
    df = pd.DataFrame({
        'time': pd.date_range('2026-01-01', periods=len(closes), freq='1min'),
        'open': closes,
        'high': highs,
        'low': lows,
        'close': closes
    })
    
    result = strategy.generate_signals(df)
    
    # Print diagnostic columns
    print("\nCalculated indicators:")
    print(result[['time', 'close', 'fast_ema', 'slow_ema', 'rsi', 'prev_rsi', 'atr', 'volatility_ok', 'ema_trend_ok', 'long_entry']])
    
    # Check that we got at least one long entry
    assert result['long_entry'].any(), "No long entry signal was generated"

def test_short_entry_trigger():
    """Verify that a short entry is triggered when all conditions align."""
    strategy = RsiEma50CrossScalperStrategy(
        fast_ema_period=3, 
        slow_ema_period=6, 
        rsi_period=2, 
        rsi_level=50.0, 
        min_atr=0.1
    )
    
    # Downward sequence
    closes = [100.0] * 15 + [100.0, 100.0, 100.0, 100.0, 100.0, 92.0, 90.0, 88.0, 86.0, 84.0]
    highs =  [100.5] * 15 + [100.5, 100.5, 100.5, 100.5, 100.5, 93.0, 91.0, 89.0, 87.0, 85.0]
    lows =   [ 99.5] * 15 + [ 99.5,  99.5,  99.5,  99.5,  99.5, 91.0, 89.0, 87.0, 85.0, 83.0]
    
    df = pd.DataFrame({
        'time': pd.date_range('2026-01-01', periods=len(closes), freq='1min'),
        'open': closes,
        'high': highs,
        'low': lows,
        'close': closes
    })
    
    result = strategy.generate_signals(df)
    
    print("\nCalculated indicators for Short:")
    print(result[['time', 'close', 'fast_ema', 'slow_ema', 'rsi', 'prev_rsi', 'atr', 'volatility_ok', 'ema_trend_ok', 'short_entry']])
    
    # Check that we got at least one short entry
    assert result['short_entry'].any(), "No short entry signal was generated"

def test_insufficient_data():
    """Verify that strategy handles small datasets gracefully without throwing exceptions."""
    strategy = RsiEma50CrossScalperStrategy()
    df = pd.DataFrame({
        'time': pd.date_range('2026-01-01', periods=5, freq='1min'),
        'open': [2000.0]*5,
        'high': [2001.0]*5,
        'low': [1999.0]*5,
        'close': [2000.0]*5
    })
    
    try:
        result = strategy.generate_signals(df)
        assert len(result) == 5
        # Signals should be false/NaN
        assert not result['long_entry'].any()
        assert not result['short_entry'].any()
    except Exception as e:
        pytest.fail(f"Strategy crashed on insufficient data: {e}")

if __name__ == "__main__":
    pytest.main([__file__])
