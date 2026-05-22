import unittest
import pandas as pd
import numpy as np
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from strategies.sma_momentum import SMAMomentumStrategy

class TestStrategyEdgeCases(unittest.TestCase):
    def setUp(self):
        self.strategy = SMAMomentumStrategy()

    def test_empty_dataframe(self):
        """Strategy should handle empty dataframe gracefully."""
        df = pd.DataFrame(columns=['time', 'close'])
        # Should raise or return empty. We check it doesn't crash.
        try:
            res = self.strategy.generate_signals(df)
            self.assertTrue(res.empty)
        except Exception as e:
            self.fail(f"Strategy crashed on empty dataframe: {e}")

    def test_zero_volume_flat_price(self):
        """Strategy should handle periods of zero price movement (NaN/Zero div checks)."""
        data = {
            'time': pd.date_range(start='2026-01-01', periods=100, freq='1min'),
            'close': [50000.0] * 100
        }
        df = pd.DataFrame(data)
        res = self.strategy.generate_signals(df)
        
        # RSI might be NaN if there's no gain/loss. Ensure signals are 0.
        self.assertEqual(res['signal'].sum(), 0)
        self.assertFalse(res['signal'].isnull().any())

    def test_insufficient_data(self):
        """Strategy should handle datasets smaller than the largest window (50)."""
        data = {
            'time': pd.date_range(start='2026-01-01', periods=10, freq='1min'),
            'close': np.random.randn(10) + 50000
        }
        df = pd.DataFrame(data)
        res = self.strategy.generate_signals(df)
        
        # Everything should be NaN or 0, but not crash
        self.assertTrue(res['sma_slow'].isnull().all())
        self.assertEqual(res['signal'].sum(), 0)

    def test_price_gap(self):
        """Strategy should handle sudden price jumps/gaps."""
        data = {
            'time': pd.date_range(start='2026-01-01', periods=100, freq='1min'),
            'close': [50000.0] * 50 + [60000.0] * 50
        }
        df = pd.DataFrame(data)
        res = self.strategy.generate_signals(df)
        
        # Should generate a signal or at least not crash
        self.assertIn('rsi', res.columns)
        self.assertFalse(res['rsi'].isnull().all())

if __name__ == '__main__':
    unittest.main()
