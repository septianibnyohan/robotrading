import unittest
from unittest.mock import MagicMock, patch
import pandas as pd
import MetaTrader5 as mt5

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import btc_layer_bot as bot

class TestLayeringStrategy(unittest.TestCase):

    def test_recover_layer_state_empty(self):
        """Verify recover_layer_state returns None when there are no positions."""
        self.assertIsNone(bot.recover_layer_state([]))

    def test_recover_layer_state_buy(self):
        """Verify recover_layer_state recovers BUY state from positions."""
        pos1 = MagicMock(time=1000, type=mt5.POSITION_TYPE_BUY, price_open=75000.0)
        pos2 = MagicMock(time=2000, type=mt5.POSITION_TYPE_BUY, price_open=74900.0)
        state = bot.recover_layer_state([pos1, pos2])
        self.assertEqual(state["direction"], "BUY")
        self.assertEqual(state["first_entry_price"], 75000.0)
        self.assertEqual(state["total_layers"], 2)

    def test_recover_layer_state_sell(self):
        """Verify recover_layer_state recovers SELL state from positions."""
        pos1 = MagicMock(time=1000, type=mt5.POSITION_TYPE_SELL, price_open=75000.0)
        state = bot.recover_layer_state([pos1])
        self.assertEqual(state["direction"], "SELL")
        self.assertEqual(state["first_entry_price"], 75000.0)
        self.assertEqual(state["total_layers"], 1)

    def test_check_h1_signal_buy(self):
        """Verify H1 BUY signal triggers when close > ema200."""
        row = {'close': 75200.0, 'ema_200': 75000.0}
        self.assertEqual(bot.check_h1_signal(row), "BUY")

    def test_check_h1_signal_sell(self):
        """Verify H1 SELL signal triggers when close < ema200."""
        row = {'close': 74800.0, 'ema_200': 75000.0}
        self.assertEqual(bot.check_h1_signal(row), "SELL")

    def test_check_h1_signal_none(self):
        """Verify no signal triggers when parameters do not align (close == ema_200)."""
        row = {'close': 75000.0, 'ema_200': 75000.0}
        self.assertIsNone(bot.check_h1_signal(row))

    def test_check_m1_crossover_up(self):
        """Verify M1 RSI crossover Buy triggers when RSI crosses above 30."""
        df = pd.DataFrame([
            {'rsi_14': 25.0},  # iloc[-3]
            {'rsi_14': 32.0},  # iloc[-2]
            {'rsi_14': 35.0}   # iloc[-1] (active)
        ])
        self.assertEqual(bot.check_m1_crossover(df), "BUY")

    def test_check_m1_crossover_down(self):
        """Verify M1 RSI crossover Sell triggers when RSI crosses below 70."""
        df = pd.DataFrame([
            {'rsi_14': 75.0},  # iloc[-3]
            {'rsi_14': 68.0},  # iloc[-2]
            {'rsi_14': 65.0}   # iloc[-1] (active)
        ])
        self.assertEqual(bot.check_m1_crossover(df), "SELL")

    def test_check_m1_crossover_none(self):
        """Verify no crossover is detected when RSI remains in bounds."""
        df = pd.DataFrame([
            {'rsi_14': 50.0},
            {'rsi_14': 52.0},
            {'rsi_14': 51.0}
        ])
        self.assertIsNone(bot.check_m1_crossover(df))

    def test_check_h1_exit_buy_and(self):
        """Verify H1 Buy exit triggers under logical AND."""
        row = {'close': 74800.0, 'ema_200': 75000.0, 'rsi_14': 38.0}
        with patch('btc_config.EXIT_LOGIC_AND', True):
            self.assertTrue(bot.check_h1_exit_conditions(row, "BUY"))

    def test_check_h1_exit_buy_and_fail(self):
        """Verify H1 Buy exit does not trigger if only one condition is met under AND."""
        row = {'close': 75200.0, 'ema_200': 75000.0, 'rsi_14': 38.0}
        with patch('btc_config.EXIT_LOGIC_AND', True):
            self.assertFalse(bot.check_h1_exit_conditions(row, "BUY"))

    def test_get_layer_step_usd(self):
        """Verify step returns LAYERING_STEP_USD in USD mode."""
        row = {'atr_14': 150.0}
        with patch('btc_config.LAYERING_MODE', 'USD'):
            self.assertEqual(bot.get_layer_step(row), bot.btc_config.LAYERING_STEP_USD)

    def test_get_layer_step_atr(self):
        """Verify step returns ATR multiplier in ATR mode."""
        row = {'atr_14': 150.0}
        with patch('btc_config.LAYERING_MODE', 'ATR'):
            self.assertEqual(bot.get_layer_step(row), 150.0 * bot.btc_config.LAYERING_STEP_ATR_MULT)

    @patch('btc_layer_bot.open_trade')
    def test_handle_layering_buy_triggered(self, mock_open_trade):
        """Verify layering opens another Buy when price drops past spacing offset."""
        mock_open_trade.return_value = 111
        state = {"direction": "BUY", "first_entry_price": 75000.0, "total_layers": 1}
        tick = MagicMock(ask=74850.0)  # offset is 1 * 100 = 100. Price is 74850 <= 74900
        bot.handle_layering([], state, 100.0, tick)
        self.assertEqual(state["total_layers"], 2)
        mock_open_trade.assert_called_once_with("BUY", 74850.0, 0.0, 0.0)

    @patch('btc_layer_bot.open_trade')
    def test_handle_layering_buy_not_triggered(self, mock_open_trade):
        """Verify layering does not open Buy if price is above spacing offset."""
        state = {"direction": "BUY", "first_entry_price": 75000.0, "total_layers": 1}
        tick = MagicMock(ask=74950.0)  # offset is 100. Price is 74950 > 74900
        bot.handle_layering([], state, 100.0, tick)
        self.assertEqual(state["total_layers"], 1)
        mock_open_trade.assert_not_called()

    @patch('btc_layer_bot.close_all_open_positions')
    def test_handle_basket_tp_triggered(self, mock_close):
        """Verify basket TP closes positions when target profit is exceeded."""
        import btc_config
        import datetime
        with patch.object(btc_config, 'TAKE_PROFIT_PER_LAYER_USD', 0.20):
            pos1 = MagicMock(symbol=btc_config.SYMBOL, profit=10.0, commission=0.0, swap=0.0)
            pos2 = MagicMock(symbol=btc_config.SYMBOL, profit=15.0, commission=0.0, swap=0.0)
            pos1.time = datetime.datetime(2026, 6, 3, 10, 0, 0).timestamp()
            pos2.time = datetime.datetime(2026, 6, 3, 10, 0, 0).timestamp()
            state = {"total_layers": 2}  # Target: 2 * 0.20 = 0.40. Profit is 25.0
            self.assertTrue(bot.handle_basket_tp([pos1, pos2], state))
            mock_close.assert_called_once_with("BASKET_TP", symbol=btc_config.SYMBOL, magic=btc_config.MAGIC_NUMBER)

    @patch('btc_layer_bot.close_all_open_positions')
    def test_handle_basket_tp_not_triggered(self, mock_close):
        """Verify basket TP does not trigger when profit is below target."""
        import btc_config
        import datetime
        with patch.object(btc_config, 'TAKE_PROFIT_PER_LAYER_USD', 0.20):
            pos1 = MagicMock(symbol=btc_config.SYMBOL, profit=-1.0, commission=0.0, swap=0.0)
            pos1.time = datetime.datetime(2026, 6, 3, 10, 0, 0).timestamp()
            state = {"total_layers": 1}  # Target: 0.20. Profit is -1.0
            self.assertFalse(bot.handle_basket_tp([pos1], state))
            mock_close.assert_not_called()

if __name__ == "__main__":
    unittest.main()
