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
        
        # Mock 1 active trade opened during normal hours (e.g. Wednesday 10:00 AM)
        pos = MagicMock(magic=20260523, symbol="BTCUSDc")
        pos.time = datetime.datetime(2026, 6, 3, 10, 0, 0).timestamp()
        mock_positions_get.return_value = [pos]
        
        # Load the normal value first by patching time as normal hours
        normal_time = datetime.datetime(2026, 6, 3, 10, 0, 0)
        with patch.object(btc_config, '_get_current_time', return_value=normal_time):
            normal_lot_size = btc_config.LOT_SIZE
        
        # Weekday evening at 16:00 (normally low-risk window)
        lowrisk_time = datetime.datetime(2026, 6, 3, 16, 0, 0)
        with patch.object(btc_config, '_get_current_time', return_value=lowrisk_time):
            # Check lot size remains normal instead of low risk
            self.assertAlmostEqual(btc_config.LOT_SIZE, normal_lot_size)

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

    @patch('MetaTrader5.terminal_info')
    @patch('MetaTrader5.positions_get')
    def test_low_risk_applied_when_only_low_risk_trades_open(self, mock_positions_get, mock_terminal_info):
        """Verify low-risk overrides are applied when open positions were all opened during low-risk hours."""
        mock_terminal_info.return_value = MagicMock()
        
        # Mock 1 active trade opened during low-risk hours (e.g. Wednesday 16:00)
        pos = MagicMock(magic=20260523, symbol="BTCUSDc")
        pos.time = datetime.datetime(2026, 6, 3, 16, 0, 0).timestamp()
        mock_positions_get.return_value = [pos]
        
        # Weekday evening at 16:00 (low-risk window)
        lowrisk_time = datetime.datetime(2026, 6, 3, 16, 0, 0)
        with patch.object(btc_config, '_get_current_time', return_value=lowrisk_time):
            # Check lot size switches to low risk (0.05) because no normal layer exists
            self.assertAlmostEqual(btc_config.LOT_SIZE, 0.05)


class TestBasketTpAdjustment(unittest.TestCase):
    @patch('btc_layer_bot.close_all_open_positions')
    @patch('MetaTrader5.positions_get')
    @patch('MetaTrader5.terminal_info')
    def test_basket_tp_with_normal_trade_active(self, mock_terminal_info, mock_positions_get, mock_close):
        """Verify target profit is calculated as normal_active_layers * tp_per_layer when a normal trade is active."""
        mock_terminal_info.return_value = MagicMock()
        
        btc_config.set_active_symbol("BTCUSDc")
        normal_time = datetime.datetime(2026, 6, 3, 10, 0, 0) # Wednesday 10 AM (normal config time)
        low_risk_time = datetime.datetime(2026, 6, 3, 16, 0, 0) # Wednesday 4 PM (low risk config time)
        
        # We have 2 normal layers and 1 low risk layer (total 3 layers)
        pos1 = MagicMock(symbol="BTCUSDc", profit=10.0, commission=0.0, swap=0.0, magic=20260523)
        pos1.time = normal_time.timestamp()
        
        pos2 = MagicMock(symbol="BTCUSDc", profit=10.0, commission=0.0, swap=0.0, magic=20260523)
        pos2.time = normal_time.timestamp()
        
        pos3 = MagicMock(symbol="BTCUSDc", profit=5.0, commission=0.0, swap=0.0, magic=20260523)
        pos3.time = low_risk_time.timestamp()
        
        # Mock positions_get
        mock_positions_get.return_value = [pos1, pos2, pos3]
        
        # Target profit should be based on normal active layers: 2 * TAKE_PROFIT_PER_LAYER_USD
        # Under normal hours, TP is 20.8 (0.20 * 104)
        with patch.object(btc_config, '_get_current_time', return_value=normal_time):
            tp_per_layer = btc_config.TAKE_PROFIT_PER_LAYER_USD
        
        target = 2 * tp_per_layer # Target profit = 41.6
        
        state = {"total_layers": 3}
        
        # Total profit is 25.0 (which is less than target 41.6) -> should return False
        self.assertFalse(btc_layer_bot.handle_basket_tp([pos1, pos2, pos3], state))
        mock_close.assert_not_called()
        
        # Update profit to meet/exceed target (e.g. pos1 profit = 30.0 -> total profit = 45.0 >= 41.6)
        pos1.profit = 30.0
        self.assertTrue(btc_layer_bot.handle_basket_tp([pos1, pos2, pos3], state))
        mock_close.assert_called_once_with("BASKET_TP", symbol="BTCUSDc", magic=20260523)

    @patch('btc_layer_bot.close_all_open_positions')
    @patch('MetaTrader5.positions_get')
    @patch('MetaTrader5.terminal_info')
    def test_basket_tp_with_only_low_risk_trades_active(self, mock_terminal_info, mock_positions_get, mock_close):
        """Verify target profit is calculated as total_layers * low_risk_tp when only low-risk trades are active."""
        mock_terminal_info.return_value = MagicMock()
        
        btc_config.set_active_symbol("BTCUSDc")
        low_risk_time = datetime.datetime(2026, 6, 3, 16, 0, 0) # Wednesday 4 PM (low risk config time)
        
        # We have 2 low risk layers
        pos1 = MagicMock(symbol="BTCUSDc", profit=1.5, commission=0.0, swap=0.0, magic=20260523)
        pos1.time = low_risk_time.timestamp()
        
        pos2 = MagicMock(symbol="BTCUSDc", profit=1.5, commission=0.0, swap=0.0, magic=20260523)
        pos2.time = low_risk_time.timestamp()
        
        mock_positions_get.return_value = [pos1, pos2]
        
        # Target profit should be based on low-risk config: 2 * low_risk_tp = 2 * (0.20 * 5) = 2.0 USD
        state = {"total_layers": 2}
        
        # Total profit is 3.0 USD (exceeds target 2.0 USD) -> should return True
        self.assertTrue(btc_layer_bot.handle_basket_tp([pos1, pos2], state))
        mock_close.assert_called_once_with("BASKET_TP", symbol="BTCUSDc", magic=20260523)
        
        mock_close.reset_mock()
        # Total profit is 1.0 USD (below target 2.0 USD) -> should return False
        pos1.profit = 0.5
        pos2.profit = 0.5
        self.assertFalse(btc_layer_bot.handle_basket_tp([pos1, pos2], state))
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
