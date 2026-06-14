import unittest
from unittest.mock import patch, MagicMock
import datetime
import sys
import os
import threading

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import btc_config
import btc_layer_bot
import btc_m5_bot
import MetaTrader5 as mt5

class TestDynamicConfigPreservation(unittest.TestCase):
    def setUp(self):
        btc_config.set_active_symbol("BTCUSDc")

    def tearDown(self):
        btc_config.set_active_symbol("BTCUSDc")

    def test_is_low_risk_time_evaluation(self):
        """Verify is_low_risk_time correctly detects normal vs low risk hours."""
        # Case 1: Weekday (Wednesday) at 16:00 (Outside peak hours -> low risk)
        lowrisk_time = datetime.datetime(2026, 6, 3, 16, 0, 0)
        with patch.object(btc_config, '_get_current_time', return_value=lowrisk_time):
            self.assertTrue(btc_config.is_low_risk_time())
            
        # Case 2: Weekday (Wednesday) at 05:00 AM (Within morning normal window -> not low risk)
        normal_time = datetime.datetime(2026, 6, 3, 5, 0, 0)
        with patch.object(btc_config, '_get_current_time', return_value=normal_time):
            self.assertFalse(btc_config.is_low_risk_time())

    @patch('MetaTrader5.terminal_info')
    @patch('MetaTrader5.positions_get')
    def test_normal_config_preserved_when_trades_open(self, mock_positions_get, mock_terminal_info):
        """Verify low-risk overrides are ignored when positions are open during low-risk hours."""
        mock_terminal_info.return_value = MagicMock()
        
        # Mock 1 active trade matching symbol and magic number
        pos = MagicMock(magic=20260523, symbol="BTCUSDc")
        mock_positions_get.return_value = [pos]
        
        # Weekday evening at 16:00 (normally low-risk window)
        lowrisk_time = datetime.datetime(2026, 6, 3, 16, 0, 0)
        with patch.object(btc_config, '_get_current_time', return_value=lowrisk_time):
            # Check lot size remains normal (1.03) instead of low risk (0.05)
            self.assertAlmostEqual(btc_config.LOT_SIZE, 1.03)

    @patch('MetaTrader5.terminal_info')
    @patch('MetaTrader5.positions_get')
    def test_low_risk_applied_when_no_trades_open(self, mock_positions_get, mock_terminal_info):
        """Verify low-risk overrides are applied when no positions are open during low-risk hours."""
        mock_terminal_info.return_value = MagicMock()
        mock_positions_get.return_value = []
        
        # Weekday evening at 16:00 (low-risk window)
        lowrisk_time = datetime.datetime(2026, 6, 3, 16, 0, 0)
        with patch.object(btc_config, '_get_current_time', return_value=lowrisk_time):
            # Check lot size switches to low risk (0.05)
            self.assertAlmostEqual(btc_config.LOT_SIZE, 0.05)


class TestBasketTpAdjustment(unittest.TestCase):
    @patch('btc_layer_bot.close_all_open_positions')
    @patch('btc_config.is_low_risk_time')
    @patch('MetaTrader5.positions_get')
    @patch('MetaTrader5.terminal_info')
    def test_basket_tp_caps_in_low_risk_hours(self, mock_terminal_info, mock_positions_get, mock_is_low_risk, mock_close):
        """Verify target profit uses number_of_normal_layer when in low-risk hours and total_layers exceeds it."""
        mock_terminal_info.return_value = MagicMock()
        mock_is_low_risk.return_value = True
        
        # Test case: total_layers = 7, number_of_normal_layer = 5.
        # target profit should be: min(7, 5) * TAKE_PROFIT_PER_LAYER_USD
        # = 5 * (0.20 * 103) = 103.0 USD.
        # If profit is 105 USD, target is met and handle_basket_tp should return True.
        # If profit is 100 USD, target is not met and should return False.
        pos1 = MagicMock(symbol="BTCUSDc", profit=105.0, commission=0.0, swap=0.0, magic=20260523)
        mock_positions_get.return_value = [pos1]
        state = {"total_layers": 7}
        
        btc_config.set_active_symbol("BTCUSDc")
        self.assertTrue(btc_layer_bot.handle_basket_tp([pos1], state))
        mock_close.assert_called_once_with("BASKET_TP", symbol="BTCUSDc", magic=20260523)
        
        mock_close.reset_mock()
        pos2 = MagicMock(symbol="BTCUSDc", profit=100.0, commission=0.0, swap=0.0, magic=20260523)
        mock_positions_get.return_value = [pos2]
        self.assertFalse(btc_layer_bot.handle_basket_tp([pos2], state))
        mock_close.assert_not_called()

    @patch('btc_layer_bot.close_all_open_positions')
    @patch('btc_config.is_low_risk_time')
    @patch('MetaTrader5.positions_get')
    @patch('MetaTrader5.terminal_info')
    def test_basket_tp_uses_total_layers_normally(self, mock_terminal_info, mock_positions_get, mock_is_low_risk, mock_close):
        """Verify target profit uses total_layers normally outside low-risk hours."""
        mock_terminal_info.return_value = MagicMock()
        mock_is_low_risk.return_value = False
        
        # Test case: total_layers = 7. Not in low risk time.
        # target profit should be calculated as: 7 * (0.20 * 103) = 144.2 USD.
        # If profit is 145 USD, target (144.2 USD) is met and handle_basket_tp should return True.
        # If profit is 140 USD, target (144.2 USD) is not met and should return False.
        pos1 = MagicMock(symbol="BTCUSDc", profit=145.0, commission=0.0, swap=0.0, magic=20260523)
        mock_positions_get.return_value = [pos1]
        state = {"total_layers": 7}
        
        btc_config.set_active_symbol("BTCUSDc")
        self.assertTrue(btc_layer_bot.handle_basket_tp([pos1], state))
        mock_close.assert_called_once_with("BASKET_TP", symbol="BTCUSDc", magic=20260523)
        
        mock_close.reset_mock()
        pos2 = MagicMock(symbol="BTCUSDc", profit=140.0, commission=0.0, swap=0.0, magic=20260523)
        mock_positions_get.return_value = [pos2]
        self.assertFalse(btc_layer_bot.handle_basket_tp([pos2], state))
        mock_close.assert_not_called()


class TestLayerBotThresholdClosing(unittest.TestCase):
    @patch('btc_layer_bot.close_all_open_positions')
    @patch('MetaTrader5.positions_get')
    @patch('MetaTrader5.symbol_info_tick')
    def test_layer_bot_closes_positions_when_exceeded(self, mock_tick, mock_positions_get, mock_close_all):
        """Verify btc_layer_bot closes all positions when count exceeds safety threshold."""
        mock_tick.return_value = MagicMock(ask=75000.0, bid=74990.0)
        
        # 11 open positions (exceeds threshold 5 * 2 = 10)
        pos_list = [MagicMock(magic=20260523) for _ in range(11)]
        mock_positions_get.return_value = pos_list
        
        stop_event = threading.Event()
        
        # Set stop_event inside close_all mock to break loop
        def mock_close_action(*args, **kwargs):
            stop_event.set()
            return True
        mock_close_all.side_effect = mock_close_action

        # Run loop with a patched time.sleep to run instantly
        with patch('time.sleep'):
            btc_layer_bot.run_trading_loop("BTCUSDc", 10000.0, stop_event)
            
        mock_close_all.assert_called_once_with("Layer Limit Exceeded", symbol="BTCUSDc", magic=20260523)


class TestM5BotThresholdClosing(unittest.TestCase):
    @patch('btc_m5_bot.close_all_open_positions')
    @patch('MetaTrader5.positions_get')
    @patch('MetaTrader5.symbol_info_tick')
    def test_m5_bot_closes_positions_when_exceeded(self, mock_tick, mock_positions_get, mock_close_all):
        """Verify btc_m5_bot closes all positions when count exceeds safety threshold."""
        mock_tick.return_value = MagicMock(ask=75000.0, bid=74990.0)
        
        # 11 open positions (exceeds threshold 5 * 2 = 10)
        pos_list = [MagicMock(magic=20260524) for _ in range(11)]
        mock_positions_get.return_value = pos_list
        
        stop_event = threading.Event()
        
        # Set stop_event inside close_all mock to break loop
        def mock_close_action(*args, **kwargs):
            stop_event.set()
            return True
        mock_close_all.side_effect = mock_close_action

        # Run loop with a patched time.sleep to run instantly
        with patch('time.sleep'):
            btc_m5_bot.run_trading_loop("BTCUSDc", 10000.0, stop_event)
            
        mock_close_all.assert_called_once_with("Layer Limit Exceeded", symbol="BTCUSDc", magic=20260524)


if __name__ == '__main__':
    unittest.main()
