import unittest
from unittest.mock import patch, MagicMock
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

class TestDynamicConfig(unittest.TestCase):
    def setUp(self):
        import btc_config
        btc_config.clear_active_risk()

    def tearDown(self):
        import btc_config
        btc_config.clear_active_risk()
        btc_config.set_active_symbol("BTCUSDc")

    def test_active_symbols_list(self):
        """Verify ACTIVE_SYMBOLS list is correctly defined in btc_config."""
        import btc_config
        self.assertEqual(btc_config.ACTIVE_SYMBOLS, ["BTCUSDc", "XAUUSDc", "BTCUSDm", "XAUUSDm", "XAGUSDc", "ETHUSDc", "EURUSDc", "EURJPYc", "ETHUSDm", "EURUSDm", "EURJPYm", "USDJPYm"])

    @patch('MetaTrader5.terminal_info', return_value=None)
    def test_dynamic_config_time_based_switching(self, mock_term_info):
        """Verify dynamic configuration switches based on time and day."""
        import btc_config
        import datetime
        from unittest.mock import patch
        import config.symbols.BTCUSDc as BTCUSDc
        import config.symbols.XAUUSDc as XAUUSDc

        # --- BTCUSD Scheduling Rules ---
        btc_config.set_active_symbol("BTCUSDc")

        # Case 1: Weekday (Wednesday) at 08:00 AM (Outside windows -> low risk config)
        wednesday_morning_1 = datetime.datetime(2026, 6, 3, 8, 0, 0)
        with patch('btc_config.DynamicConfigModule._get_current_time', return_value=wednesday_morning_1):
            self.assertAlmostEqual(btc_config.LOT_SIZE, BTCUSDc.LOW_RISK_OVERRIDES["LOT_SIZE"])
            self.assertAlmostEqual(btc_config.LAYERING_STEP_ATR_MULT, BTCUSDc.LOW_RISK_OVERRIDES["LAYERING_STEP_ATR_MULT"])

        # Case 2: Weekday (Wednesday) at 15:00 PM (Within 12:00 - 20:00 moderate window)
        wednesday_morning_2 = datetime.datetime(2026, 6, 3, 15, 0, 0)
        with patch('btc_config.DynamicConfigModule._get_current_time', return_value=wednesday_morning_2):
            self.assertAlmostEqual(btc_config.LOT_SIZE, BTCUSDc.MODERATE_RISK_OVERRIDES["LOT_SIZE"])
            self.assertAlmostEqual(btc_config.LAYERING_STEP_ATR_MULT, BTCUSDc.MODERATE_RISK_OVERRIDES["LAYERING_STEP_ATR_MULT"])
 
        # Case 3: Weekday (Wednesday) at 21:00 PM (Outside windows -> low risk config)
        wednesday_evening = datetime.datetime(2026, 6, 3, 21, 0, 0)
        with patch('btc_config.DynamicConfigModule._get_current_time', return_value=wednesday_evening):
            self.assertAlmostEqual(btc_config.LOT_SIZE, BTCUSDc.LOW_RISK_OVERRIDES["LOT_SIZE"])
            self.assertAlmostEqual(btc_config.LAYERING_STEP_ATR_MULT, BTCUSDc.LOW_RISK_OVERRIDES["LAYERING_STEP_ATR_MULT"])
 
        # Case 4: Weekday (Wednesday) at 23:00 PM (Within 22:00 - 01:00 normal window)
        wednesday_night = datetime.datetime(2026, 6, 3, 23, 0, 0)
        with patch('btc_config.DynamicConfigModule._get_current_time', return_value=wednesday_night):
            self.assertAlmostEqual(btc_config.LOT_SIZE, BTCUSDc.LOT_SIZE)
            self.assertAlmostEqual(btc_config.LAYERING_STEP_ATR_MULT, BTCUSDc.LAYERING_STEP_ATR_MULT)

        # --- XAUUSD Scheduling Rules ---
        btc_config.set_active_symbol("XAUUSDc")

        # Case 5: Weekday (Wednesday) at 02:00 AM (Within 01:00 - 05:00 normal window)
        xau_normal_time = datetime.datetime(2026, 6, 3, 2, 0, 0)
        with patch('btc_config.DynamicConfigModule._get_current_time', return_value=xau_normal_time):
            self.assertAlmostEqual(btc_config.LAYERING_STEP_ATR_MULT, XAUUSDc.LAYERING_STEP_ATR_MULT)

        # Case 6: Weekday (Wednesday) at 23:00 PM (Within 22:00 - 04:00 moderate window, outside normal)
        xau_moderate_time = datetime.datetime(2026, 6, 3, 23, 0, 0)
        with patch('btc_config.DynamicConfigModule._get_current_time', return_value=xau_moderate_time):
            self.assertAlmostEqual(btc_config.LAYERING_STEP_ATR_MULT, XAUUSDc.MODERATE_RISK_OVERRIDES["LAYERING_STEP_ATR_MULT"])

        # Case 6b: Weekday (Wednesday) at 12:00 PM (Outside windows -> low risk)
        xau_lowrisk_time = datetime.datetime(2026, 6, 3, 12, 0, 0)
        with patch('btc_config.DynamicConfigModule._get_current_time', return_value=xau_lowrisk_time):
            self.assertAlmostEqual(btc_config.LAYERING_STEP_ATR_MULT, XAUUSDc.LOW_RISK_OVERRIDES["LAYERING_STEP_ATR_MULT"])

        # --- XAGUSD Scheduling Rules ---
        import config.symbols.XAGUSDc as XAGUSDc
        btc_config.set_active_symbol("XAGUSDc")

        # Case 7: Weekday (Wednesday) at 03:00 AM (Within 02:00 - 06:00 normal window)
        xag_normal_time = datetime.datetime(2026, 6, 3, 3, 0, 0)
        with patch('btc_config.DynamicConfigModule._get_current_time', return_value=xag_normal_time):
            self.assertAlmostEqual(btc_config.LAYERING_STEP_ATR_MULT, XAGUSDc.LAYERING_STEP_ATR_MULT)

        # Case 8: Weekday (Wednesday) at 15:00 PM (Within 12:00 - 18:00 moderate window)
        xag_moderate_time = datetime.datetime(2026, 6, 3, 15, 0, 0)
        with patch('btc_config.DynamicConfigModule._get_current_time', return_value=xag_moderate_time):
            self.assertAlmostEqual(btc_config.LAYERING_STEP_ATR_MULT, XAGUSDc.MODERATE_RISK_OVERRIDES["LAYERING_STEP_ATR_MULT"])

        # Case 8b: Weekday (Wednesday) at 01:00 AM (Outside windows -> low risk)
        xag_lowrisk_time = datetime.datetime(2026, 6, 3, 1, 0, 0)
        with patch('btc_config.DynamicConfigModule._get_current_time', return_value=xag_lowrisk_time):
            self.assertAlmostEqual(btc_config.LAYERING_STEP_ATR_MULT, XAGUSDc.LOW_RISK_OVERRIDES["LAYERING_STEP_ATR_MULT"])

        # --- ETHUSD Scheduling Rules ---
        import config.symbols.ETHUSDc as ETHUSDc
        btc_config.set_active_symbol("ETHUSDc")

        # Case 9: Weekday (Wednesday) at 02:00 AM (Within 00:00 - 02:59 normal window)
        eth_normal_time = datetime.datetime(2026, 6, 3, 2, 0, 0)
        with patch('btc_config.DynamicConfigModule._get_current_time', return_value=eth_normal_time):
            self.assertAlmostEqual(btc_config.LOT_SIZE, ETHUSDc.LOT_SIZE)

        # Case 10: Weekday (Wednesday) at 06:00 AM (Within 05:00 - 10:59 moderate window)
        eth_moderate_time = datetime.datetime(2026, 6, 3, 6, 0, 0)
        with patch('btc_config.DynamicConfigModule._get_current_time', return_value=eth_moderate_time):
            self.assertAlmostEqual(btc_config.LOT_SIZE, ETHUSDc.MODERATE_RISK_OVERRIDES["LOT_SIZE"])

        # Case 10b: Weekday (Wednesday) at 15:00 PM (Outside windows -> low risk)
        eth_lowrisk_time = datetime.datetime(2026, 6, 3, 15, 0, 0)
        with patch('btc_config.DynamicConfigModule._get_current_time', return_value=eth_lowrisk_time):
            self.assertAlmostEqual(btc_config.LOT_SIZE, ETHUSDc.LOW_RISK_OVERRIDES["LOT_SIZE"])

        # Clean up by resetting active symbol to default
        btc_config.set_active_symbol("BTCUSDc")

    def test_dynamic_config_context_isolation(self):
        """Verify that separate threads/contexts can maintain separate active symbols concurrently."""
        import btc_config
        import threading
        import time
        import datetime
        from unittest.mock import patch
        import config.symbols.BTCUSDc as BTCUSDc
        import config.symbols.XAUUSDc as XAUUSDc

        results = {}

        def thread_task(symbol_name, sleep_time):
            btc_config.set_active_symbol(symbol_name)
            time.sleep(sleep_time)
            # Retrieve values after sleep to ensure other threads did not overwrite it
            results[symbol_name] = {
                "symbol": btc_config.SYMBOL,
                "lot_size": btc_config.LOT_SIZE,
            }

        # Mock risk level to normal so both symbols use their normal configuration
        with patch.object(btc_config, 'get_risk_level', return_value="normal"):
            t1 = threading.Thread(target=thread_task, args=("BTCUSDc", 0.2))
            t2 = threading.Thread(target=thread_task, args=("XAUUSDc", 0.1))

            t1.start()
            # Give t1 a head start to set to BTCUSDc
            time.sleep(0.05)
            t2.start()

            t1.join()
            t2.join()

        # Both contexts should resolve to their respective symbol configs correctly
        self.assertEqual(results["BTCUSDc"]["symbol"], "BTCUSDc")
        self.assertAlmostEqual(results["BTCUSDc"]["lot_size"], BTCUSDc.LOT_SIZE)
        
        self.assertEqual(results["XAUUSDc"]["symbol"], "XAUUSDc")
        self.assertAlmostEqual(results["XAUUSDc"]["lot_size"], XAUUSDc.LOT_SIZE)


class TestBtcTrading(unittest.TestCase):
    @patch('MetaTrader5.positions_get')
    @patch('btc_trading.close_position_by_ticket')
    def test_close_all_open_positions_with_symbol(self, mock_close_ticket, mock_positions_get):
        """Verify close_all_open_positions filters by symbol correctly."""
        from btc_trading import close_all_open_positions, close_all_open_position
        
        # Mock some open positions
        mock_pos1 = MagicMock()
        mock_pos1.ticket = 11111
        mock_pos1.volume = 0.01
        mock_pos1.type = 0  # BUY
        mock_pos1.symbol = "XAUUSDc"
        mock_pos1.magic = 20260606
        
        mock_positions_get.return_value = [mock_pos1]
        
        # Test close_all_open_positions with specific symbol
        close_all_open_positions("BASKET_TP", symbol="XAUUSDc")
        
        mock_positions_get.assert_called_once_with(symbol="XAUUSDc")
        mock_close_ticket.assert_called_once_with(11111, 0.01, 0, "BASKET_TP", symbol="XAUUSDc")
        
        # Test the alias function close_all_open_position
        mock_positions_get.reset_mock()
        mock_close_ticket.reset_mock()
        
        mock_pos2 = MagicMock()
        mock_pos2.ticket = 22222
        mock_pos2.volume = 0.52
        mock_pos2.type = 0  # BUY
        mock_pos2.symbol = "BTCUSDc"
        mock_pos2.magic = 20260523
        
        mock_positions_get.return_value = [mock_pos2]
        
        close_all_open_position("BASKET_TP", symbol="BTCUSDc")
        mock_positions_get.assert_called_once_with(symbol="BTCUSDc")
        mock_close_ticket.assert_called_once_with(22222, 0.52, 0, "BASKET_TP", symbol="BTCUSDc")


if __name__ == '__main__':
    from unittest.mock import MagicMock
    unittest.main()
