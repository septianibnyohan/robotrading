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

    def test_btc_risk_level_evaluation(self):
        """Verify get_risk_level correctly detects normal vs moderate vs low risk hours for BTCUSD."""
        btc_config.set_active_symbol("BTCUSDc")
        try:
            # Case 1: 02:00 WIB -> Normal risk (between 01:00 and 05:00)
            t_normal = datetime.datetime(2026, 6, 3, 2, 0, 0)
            with patch.object(btc_config, '_get_current_time', return_value=t_normal):
                self.assertEqual(btc_config.get_risk_level(), "normal")
                self.assertFalse(btc_config.is_low_risk_time())
                
            # Case 2: 12:00 WIB -> Moderate risk (between 11:00 and 17:00)
            t_moderate = datetime.datetime(2026, 6, 3, 12, 0, 0)
            with patch.object(btc_config, '_get_current_time', return_value=t_moderate):
                self.assertEqual(btc_config.get_risk_level(), "moderate")
                self.assertFalse(btc_config.is_low_risk_time())
                
            # Case 3: 08:00 WIB -> Low risk (other times)
            t_low = datetime.datetime(2026, 6, 3, 8, 0, 0)
            with patch.object(btc_config, '_get_current_time', return_value=t_low):
                self.assertEqual(btc_config.get_risk_level(), "low")
                self.assertTrue(btc_config.is_low_risk_time())
        finally:
            btc_config.set_active_symbol("BTCUSDc")

    def test_is_low_risk_time_evaluation(self):
        """Verify is_low_risk_time correctly detects normal/moderate vs low risk hours."""
        # Wednesday at 12:00 PM (Within moderate window -> not low risk)
        moderate_time = datetime.datetime(2026, 6, 3, 12, 0, 0)
        with patch.object(btc_config, '_get_current_time', return_value=moderate_time):
            self.assertFalse(btc_config.is_low_risk_time())
            
        # Wednesday at 08:00 AM (Outside windows -> low risk)
        lowrisk_time = datetime.datetime(2026, 6, 3, 8, 0, 0)
        with patch.object(btc_config, '_get_current_time', return_value=lowrisk_time):
            self.assertTrue(btc_config.is_low_risk_time())

        # Wednesday at 02:00 AM (Within normal window -> not low risk)
        normal_time = datetime.datetime(2026, 6, 3, 2, 0, 0)
        with patch.object(btc_config, '_get_current_time', return_value=normal_time):
            self.assertFalse(btc_config.is_low_risk_time())

        # XAUUSD scheduling cases
        btc_config.set_active_symbol("XAUUSDc")
        try:
            # 11:00 WIB (Within 10:00 - 14:00 window -> normal config)
            time_11 = datetime.datetime(2026, 6, 3, 11, 0, 0)
            with patch.object(btc_config, '_get_current_time', return_value=time_11):
                self.assertEqual(btc_config.get_risk_level(), "normal")
                self.assertFalse(btc_config.is_low_risk_time())

            # 17:00 WIB (Within 16:00 - 02:00 window -> moderate config)
            time_17 = datetime.datetime(2026, 6, 3, 17, 0, 0)
            with patch.object(btc_config, '_get_current_time', return_value=time_17):
                self.assertEqual(btc_config.get_risk_level(), "moderate")
                self.assertFalse(btc_config.is_low_risk_time())

            # 15:00 WIB (Outside windows -> low risk)
            time_15 = datetime.datetime(2026, 6, 3, 15, 0, 0)
            with patch.object(btc_config, '_get_current_time', return_value=time_15):
                self.assertEqual(btc_config.get_risk_level(), "low")
                self.assertTrue(btc_config.is_low_risk_time())
        finally:
            btc_config.set_active_symbol("BTCUSDc")

        # XAGUSD scheduling cases
        btc_config.set_active_symbol("XAGUSDc")
        try:
            # 01:00 WIB (Within 00:00 - 03:00 window -> normal config)
            time_01 = datetime.datetime(2026, 6, 3, 1, 0, 0)
            with patch.object(btc_config, '_get_current_time', return_value=time_01):
                self.assertEqual(btc_config.get_risk_level(), "normal")
                self.assertFalse(btc_config.is_low_risk_time())

            # 08:00 WIB (Within 04:00 - 13:00 window -> moderate config)
            time_08 = datetime.datetime(2026, 6, 3, 8, 0, 0)
            with patch.object(btc_config, '_get_current_time', return_value=time_08):
                self.assertEqual(btc_config.get_risk_level(), "moderate")
                self.assertFalse(btc_config.is_low_risk_time())

            # 15:00 WIB (Outside windows -> low risk)
            time_15_xag = datetime.datetime(2026, 6, 3, 15, 0, 0)
            with patch.object(btc_config, '_get_current_time', return_value=time_15_xag):
                self.assertEqual(btc_config.get_risk_level(), "low")
                self.assertTrue(btc_config.is_low_risk_time())
        finally:
            btc_config.set_active_symbol("BTCUSDc")

    @patch('MetaTrader5.terminal_info')
    @patch('MetaTrader5.positions_get')
    def test_low_risk_override_priority(self, mock_positions_get, mock_terminal_info):
        """Verify low-risk takes priority over normal and moderate risk open positions."""
        mock_terminal_info.return_value = MagicMock()
        
        # Mock 2 active trades: 1 normal (02:00 AM) and 1 low-risk (08:00 AM)
        pos1 = MagicMock(magic=20260523, symbol="BTCUSDc")
        pos1.time = datetime.datetime(2026, 6, 3, 2, 0, 0).timestamp()
        
        pos2 = MagicMock(magic=20260523, symbol="BTCUSDc")
        pos2.time = datetime.datetime(2026, 6, 3, 8, 0, 0).timestamp()
        
        mock_positions_get.return_value = [pos1, pos2]
        
        # Current time is normal hours (02:00 AM)
        normal_time = datetime.datetime(2026, 6, 3, 2, 0, 0)
        with patch.object(btc_config, '_get_current_time', return_value=normal_time):
            # Check lot size remains low risk override because a low-risk position is active
            import config.symbols.BTCUSDc as BTCUSDc
            self.assertAlmostEqual(btc_config.LOT_SIZE, BTCUSDc.LOW_RISK_OVERRIDES["LOT_SIZE"])

    @patch('MetaTrader5.terminal_info')
    @patch('MetaTrader5.positions_get')
    def test_normal_config_preserved_when_trades_open(self, mock_positions_get, mock_terminal_info):
        """Verify normal overrides are preserved when normal positions are open during low-risk hours."""
        mock_terminal_info.return_value = MagicMock()
        
        # Mock 1 active trade opened during normal hours (e.g. Wednesday 02:00 AM)
        pos = MagicMock(magic=20260523, symbol="BTCUSDc")
        pos.time = datetime.datetime(2026, 6, 3, 2, 0, 0).timestamp()
        mock_positions_get.return_value = [pos]
        
        # Load the normal value first by patching time as normal hours
        normal_time = datetime.datetime(2026, 6, 3, 2, 0, 0)
        with patch.object(btc_config, '_get_current_time', return_value=normal_time):
            normal_lot_size = btc_config.LOT_SIZE
        
        # Low risk hour (08:00 AM)
        lowrisk_time = datetime.datetime(2026, 6, 3, 8, 0, 0)
        with patch.object(btc_config, '_get_current_time', return_value=lowrisk_time):
            # Check lot size remains normal instead of low risk
            self.assertAlmostEqual(btc_config.LOT_SIZE, normal_lot_size)

    @patch('MetaTrader5.terminal_info')
    @patch('MetaTrader5.positions_get')
    def test_low_risk_preserved_when_trades_open(self, mock_positions_get, mock_terminal_info):
        """Verify low-risk overrides are preserved when low-risk positions are open during normal-risk hours."""
        mock_terminal_info.return_value = MagicMock()
        
        # Mock 1 active trade opened during low risk hours (e.g. Wednesday 08:00 AM)
        pos = MagicMock(magic=20260523, symbol="BTCUSDc")
        pos.time = datetime.datetime(2026, 6, 3, 8, 0, 0).timestamp()
        mock_positions_get.return_value = [pos]
        
        # Normal risk hour (02:00 AM)
        normal_time = datetime.datetime(2026, 6, 3, 2, 0, 0)
        with patch.object(btc_config, '_get_current_time', return_value=normal_time):
            # Check lot size remains low risk instead of normal risk
            import config.symbols.BTCUSDc as BTCUSDc
            self.assertAlmostEqual(btc_config.LOT_SIZE, BTCUSDc.LOW_RISK_OVERRIDES["LOT_SIZE"])

    @patch('MetaTrader5.terminal_info')
    @patch('MetaTrader5.positions_get')
    def test_moderate_risk_preserved_when_trades_open(self, mock_positions_get, mock_terminal_info):
        """Verify moderate overrides are preserved when moderate positions are open during normal-risk hours."""
        mock_terminal_info.return_value = MagicMock()
        
        # Mock 1 active trade opened during moderate risk hours (e.g. Wednesday 12:00 PM)
        pos = MagicMock(magic=20260523, symbol="BTCUSDc")
        pos.time = datetime.datetime(2026, 6, 3, 12, 0, 0).timestamp()
        mock_positions_get.return_value = [pos]
        
        # Normal risk hour (02:00 AM)
        normal_time = datetime.datetime(2026, 6, 3, 2, 0, 0)
        with patch.object(btc_config, '_get_current_time', return_value=normal_time):
            # Check lot size remains moderate risk instead of normal risk
            import config.symbols.BTCUSDc as BTCUSDc
            self.assertAlmostEqual(btc_config.LOT_SIZE, BTCUSDc.MODERATE_RISK_OVERRIDES["LOT_SIZE"])

    @patch('MetaTrader5.terminal_info')
    @patch('MetaTrader5.positions_get')
    def test_low_risk_applied_when_no_trades_open(self, mock_positions_get, mock_terminal_info):
        """Verify low-risk overrides are applied when no positions are open during low-risk hours."""
        mock_terminal_info.return_value = MagicMock()
        mock_positions_get.return_value = []
        
        # Wednesday at 08:00 AM (low-risk window)
        lowrisk_time = datetime.datetime(2026, 6, 3, 8, 0, 0)
        with patch.object(btc_config, '_get_current_time', return_value=lowrisk_time):
            # Check lot size switches to low risk override dynamically
            import config.symbols.BTCUSDc as BTCUSDc
            self.assertAlmostEqual(btc_config.LOT_SIZE, BTCUSDc.LOW_RISK_OVERRIDES["LOT_SIZE"])


class TestBasketTpAdjustment(unittest.TestCase):
    def setUp(self):
        btc_config.set_active_symbol("BTCUSDc")

    def tearDown(self):
        btc_config.set_active_symbol("BTCUSDc")

    @patch('btc_layer_bot.close_all_open_positions')
    @patch('MetaTrader5.positions_get')
    @patch('MetaTrader5.terminal_info')
    def test_basket_tp_with_normal_trade_active(self, mock_terminal_info, mock_positions_get, mock_close):
        """Verify target profit is calculated as normal_tp * total_layers when only normal trades are active."""
        mock_terminal_info.return_value = MagicMock()
        
        normal_time = datetime.datetime(2026, 6, 3, 2, 0, 0) # Wednesday 2 AM (normal config time)
        
        # We have 2 normal layers
        pos1 = MagicMock(symbol="BTCUSDc", profit=10.0, commission=0.0, swap=0.0, magic=20260523)
        pos1.time = normal_time.timestamp()
        
        pos2 = MagicMock(symbol="BTCUSDc", profit=10.0, commission=0.0, swap=0.0, magic=20260523)
        pos2.time = normal_time.timestamp()
        
        # Mock positions_get
        mock_positions_get.return_value = [pos1, pos2]
        
        # Target profit should be based on normal active layers: 2 * TAKE_PROFIT_PER_LAYER_USD
        import config.symbols.BTCUSDc as BTCUSDc
        tp_per_layer = BTCUSDc.TAKE_PROFIT_PER_LAYER_USD
        target = 2 * tp_per_layer
        
        state = {"total_layers": 2}
        
        # Total profit is 20.0 (which is less than target) -> should return False
        self.assertFalse(btc_layer_bot.handle_basket_tp([pos1, pos2], state))
        mock_close.assert_not_called()
        
        # Update profit to meet/exceed target
        pos1.profit = target + 5.0
        self.assertTrue(btc_layer_bot.handle_basket_tp([pos1, pos2], state))
        mock_close.assert_called_once_with("BASKET_TP", symbol="BTCUSDc", magic=20260523)

    @patch('btc_layer_bot.close_all_open_positions')
    @patch('MetaTrader5.positions_get')
    @patch('MetaTrader5.terminal_info')
    def test_basket_tp_with_normal_and_low_risk_trades_active(self, mock_terminal_info, mock_positions_get, mock_close):
        """Verify target profit is forced to low-risk (low_risk_tp * total_layers) if any low-risk trade is active."""
        mock_terminal_info.return_value = MagicMock()
        
        normal_time = datetime.datetime(2026, 6, 3, 2, 0, 0) # Normal risk
        low_risk_time = datetime.datetime(2026, 6, 3, 8, 0, 0) # Low risk
        
        # We have 1 normal layer and 1 low risk layer
        pos1 = MagicMock(symbol="BTCUSDc", profit=10.0, commission=0.0, swap=0.0, magic=20260523)
        pos1.time = normal_time.timestamp()
        
        pos2 = MagicMock(symbol="BTCUSDc", profit=10.0, commission=0.0, swap=0.0, magic=20260523)
        pos2.time = low_risk_time.timestamp()
        
        mock_positions_get.return_value = [pos1, pos2]
        
        import config.symbols.BTCUSDc as BTCUSDc
        low_risk_tp = BTCUSDc.LOW_RISK_OVERRIDES["TAKE_PROFIT_PER_LAYER_USD"]
        target = 2 * low_risk_tp
        
        state = {"total_layers": 2}
        
        self.assertFalse(btc_layer_bot.handle_basket_tp([pos1, pos2], state))
        mock_close.assert_not_called()
        
        pos1.profit = target + 5.0
        self.assertTrue(btc_layer_bot.handle_basket_tp([pos1, pos2], state))
        mock_close.assert_called_once_with("BASKET_TP", symbol="BTCUSDc", magic=20260523)

    @patch('btc_layer_bot.close_all_open_positions')
    @patch('MetaTrader5.positions_get')
    @patch('MetaTrader5.terminal_info')
    def test_basket_tp_with_only_low_risk_trades_active(self, mock_terminal_info, mock_positions_get, mock_close):
        """Verify target profit is calculated as total_layers * low_risk_tp when only low-risk trades are active."""
        mock_terminal_info.return_value = MagicMock()
        
        low_risk_time = datetime.datetime(2026, 6, 3, 8, 0, 0) # Wednesday 8 AM (low risk config time)
        
        # We have 2 low risk layers
        pos1 = MagicMock(symbol="BTCUSDc", profit=1.5, commission=0.0, swap=0.0, magic=20260523)
        pos1.time = low_risk_time.timestamp()
        
        pos2 = MagicMock(symbol="BTCUSDc", profit=1.5, commission=0.0, swap=0.0, magic=20260523)
        pos2.time = low_risk_time.timestamp()
        
        mock_positions_get.return_value = [pos1, pos2]
        
        # Target profit should be based on low-risk config: 2 * low_risk_tp
        import config.symbols.BTCUSDc as BTCUSDc
        low_risk_tp = BTCUSDc.LOW_RISK_OVERRIDES["TAKE_PROFIT_PER_LAYER_USD"]
        target = 2 * low_risk_tp
        
        state = {"total_layers": 2}
        
        # Set profits to exceed target
        pos1.profit = target / 2 + 1.0
        pos2.profit = target / 2 + 1.0
        self.assertTrue(btc_layer_bot.handle_basket_tp([pos1, pos2], state))
        mock_close.assert_called_once_with("BASKET_TP", symbol="BTCUSDc", magic=20260523)
        
        mock_close.reset_mock()
        # Below target
        pos1.profit = 0.1
        pos2.profit = 0.1
        self.assertFalse(btc_layer_bot.handle_basket_tp([pos1, pos2], state))
        mock_close.assert_not_called()

    @patch('btc_layer_bot.close_all_open_positions')
    @patch('MetaTrader5.positions_get')
    @patch('MetaTrader5.terminal_info')
    def test_basket_tp_with_moderate_risk_trade_active(self, mock_terminal_info, mock_positions_get, mock_close):
        """Verify target profit is calculated based on moderate risk when moderate is the highest risk."""
        mock_terminal_info.return_value = MagicMock()
        
        moderate_time = datetime.datetime(2026, 6, 3, 12, 0, 0) # Wednesday 12 PM (moderate risk config time)
        
        pos1 = MagicMock(symbol="BTCUSDc", profit=1.5, commission=0.0, swap=0.0, magic=20260523)
        pos1.time = moderate_time.timestamp()
        
        pos2 = MagicMock(symbol="BTCUSDc", profit=1.5, commission=0.0, swap=0.0, magic=20260523)
        pos2.time = moderate_time.timestamp()
        
        mock_positions_get.return_value = [pos1, pos2]
        
        import config.symbols.BTCUSDc as BTCUSDc
        moderate_tp = BTCUSDc.MODERATE_RISK_OVERRIDES["TAKE_PROFIT_PER_LAYER_USD"]
        target = 2 * moderate_tp
        
        state = {"total_layers": 2}
        
        # Set profits to exceed target
        pos1.profit = target / 2 + 1.0
        pos2.profit = target / 2 + 1.0
        self.assertTrue(btc_layer_bot.handle_basket_tp([pos1, pos2], state))
        mock_close.assert_called_once_with("BASKET_TP", symbol="BTCUSDc", magic=20260523)


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
