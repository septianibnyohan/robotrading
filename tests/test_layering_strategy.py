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
        """Verify M1 RSI crossover Buy triggers when RSI crosses above 20."""
        df = pd.DataFrame([
            {'rsi_14': 18.0},  # iloc[-3]
            {'rsi_14': 22.0},  # iloc[-2]
            {'rsi_14': 25.0}   # iloc[-1] (active)
        ])
        self.assertEqual(bot.check_m1_crossover(df), "BUY")

    def test_check_m1_crossover_down(self):
        """Verify M1 RSI crossover Sell triggers when RSI crosses below 80."""
        df = pd.DataFrame([
            {'rsi_14': 82.0},  # iloc[-3]
            {'rsi_14': 78.0},  # iloc[-2]
            {'rsi_14': 75.0}   # iloc[-1] (active)
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
        mock_open_trade.assert_called_once_with("BUY", 74850.0, 0.0, 0.0, magic=bot.btc_config.MAGIC_NUMBER)

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
        import config.symbols.BTCUSDc as symbol_cfg
        with patch.object(symbol_cfg, 'TAKE_PROFIT_PER_LAYER_USD', 0.20):
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
        import config.symbols.BTCUSDc as symbol_cfg
        with patch.object(symbol_cfg, 'TAKE_PROFIT_PER_LAYER_USD', 0.20):
            pos1 = MagicMock(symbol=btc_config.SYMBOL, profit=-1.0, commission=0.0, swap=0.0)
            pos1.time = datetime.datetime(2026, 6, 3, 10, 0, 0).timestamp()
            state = {"total_layers": 1}  # Target: 0.20. Profit is -1.0
            self.assertFalse(bot.handle_basket_tp([pos1], state))
            mock_close.assert_not_called()

    @patch('MetaTrader5.copy_rates_from_pos')
    @patch('btc_layer_bot.rates_to_df')
    @patch('btc_layer_bot.calculate_h1_layer_indicators')
    @patch('btc_layer_bot.calculate_m1_layer_indicators')
    def test_fetch_indicators_data_timeframes(self, mock_calc_m1, mock_calc_h1, mock_rates_to_df, mock_copy_rates):
        """Verify fetch_indicators_data uses H1, M1, M5, and M15 for all symbols."""
        import btc_config
        
        mock_copy_rates.return_value = [1, 2, 3, 4]
        mock_rates_to_df.return_value = pd.DataFrame()
        mock_calc_h1.return_value = pd.DataFrame()
        mock_calc_m1.return_value = pd.DataFrame()

        # Test with BTCUSDc (should call H1, M1, M5, and M15)
        with patch('btc_config.SYMBOL', 'BTCUSDc'):
            bot.fetch_indicators_data()
            calls = mock_copy_rates.call_args_list
            self.assertEqual(calls[0][0][1], mt5.TIMEFRAME_H1)
            self.assertEqual(calls[1][0][1], mt5.TIMEFRAME_M1)
            self.assertEqual(calls[2][0][1], mt5.TIMEFRAME_M5)
            self.assertEqual(calls[3][0][1], mt5.TIMEFRAME_M15)

        mock_copy_rates.reset_mock()

        # Test with XAGUSDc (should call H1, M1, M5, and M15)
        with patch('btc_config.SYMBOL', 'XAGUSDc'):
            bot.fetch_indicators_data()
            calls = mock_copy_rates.call_args_list
            self.assertEqual(calls[0][0][1], mt5.TIMEFRAME_H1)
            self.assertEqual(calls[1][0][1], mt5.TIMEFRAME_M1)
            self.assertEqual(calls[2][0][1], mt5.TIMEFRAME_M5)
            self.assertEqual(calls[3][0][1], mt5.TIMEFRAME_M15)

    @patch('MetaTrader5.positions_get')
    @patch('MetaTrader5.symbol_info_tick')
    @patch('btc_layer_bot.fetch_indicators_data')
    @patch('btc_layer_bot.process_loop_logic')
    def test_run_trading_loop_m1_m5_prioritization(self, mock_process_loop, mock_fetch_indicators, mock_tick, mock_positions_get):
        """Verify run_trading_loop correctly prioritizes M15 over M5, and M5 over M1 positions, using the correct magic_number."""
        import btc_config
        
        # Setup mocks
        tick_mock = MagicMock()
        mock_tick.return_value = tick_mock
        
        # Mock non-empty dataframes to avoid IndexError on iloc[-2]
        mock_h1_df = pd.DataFrame([
            {'time': 1, 'close': 100.0, 'ema_200': 90.0, 'atr_14': 1.0},
            {'time': 2, 'close': 101.0, 'ema_200': 91.0, 'atr_14': 1.1}
        ])
        mock_m1_df = pd.DataFrame([
            {'time': 1, 'rsi_14': 50.0},
            {'time': 2, 'rsi_14': 52.0}
        ])
        mock_fetch_indicators.return_value = (mock_h1_df, mock_m1_df, mock_m1_df, mock_m1_df)
        
        # 1. When M1, M5, and M15 positions exist, prioritize M15
        pos_m1 = MagicMock(magic=btc_config.MAGIC_NUMBER, ticket=101)
        pos_m5 = MagicMock(magic=getattr(btc_config, 'MAGIC_NUMBER_M5', 20260524), ticket=102)
        pos_m15 = MagicMock(magic=getattr(btc_config, 'MAGIC_NUMBER_M15', 20260533), ticket=103)
        mock_positions_get.return_value = [pos_m1, pos_m5, pos_m15]
        
        stop_event = MagicMock()
        stop_event.is_set.side_effect = [False, True]  # Run exactly once
        
        with patch('btc_layer_bot.is_spread_valid', return_value=True):
            bot.run_trading_loop('BTCUSDc', 100000.0, stop_event)
            
        mock_process_loop.assert_called_once()
        passed_positions = mock_process_loop.call_args[0][0]
        self.assertEqual(len(passed_positions), 1)
        self.assertEqual(passed_positions[0].ticket, 103)

        # 2. When only M1 and M5 positions exist, prioritize M5
        mock_process_loop.reset_mock()
        mock_positions_get.return_value = [pos_m1, pos_m5]
        stop_event.is_set.side_effect = [False, True]
        
        with patch('btc_layer_bot.is_spread_valid', return_value=True):
            bot.run_trading_loop('BTCUSDc', 100000.0, stop_event)
            
        mock_process_loop.assert_called_once()
        passed_positions = mock_process_loop.call_args[0][0]
        self.assertEqual(len(passed_positions), 1)
        self.assertEqual(passed_positions[0].ticket, 102)

        # 3. When only M1 positions exist, prioritize M1
        mock_process_loop.reset_mock()
        mock_positions_get.return_value = [pos_m1]
        stop_event.is_set.side_effect = [False, True]
        
        with patch('btc_layer_bot.is_spread_valid', return_value=True):
            bot.run_trading_loop('BTCUSDc', 100000.0, stop_event)
            
        passed_positions = mock_process_loop.call_args[0][0]
        self.assertEqual(len(passed_positions), 1)
        self.assertEqual(passed_positions[0].ticket, 101)

    @patch('btc_config.ACTIVE_SYMBOL', 'XAGUSDc')
    @patch('btc_indicators.get_dxy_h1_latest_ema200')
    def test_check_h1_signal_xagusd_buy(self, mock_dxy):
        """Verify XAGUSD H1 Buy condition when XAGUSD > EMA200 and DXY < EMA200."""
        row = {'close': 30.0, 'ema_200': 29.0}
        mock_dxy.return_value = (100.0, 101.0)  # Close < EMA200
        self.assertEqual(bot.check_h1_signal(row), "BUY")

    @patch('btc_config.ACTIVE_SYMBOL', 'XAGUSDc')
    @patch('btc_indicators.get_dxy_h1_latest_ema200')
    def test_check_h1_signal_xagusd_sell(self, mock_dxy):
        """Verify XAGUSD H1 Sell condition when XAGUSD < EMA200 and DXY > EMA200."""
        row = {'close': 28.0, 'ema_200': 29.0}
        mock_dxy.return_value = (102.0, 101.0)  # Close > EMA200
        self.assertEqual(bot.check_h1_signal(row), "SELL")

    @patch('btc_config.ACTIVE_SYMBOL', 'XAGUSDc')
    @patch('btc_indicators.get_dxy_h1_latest_ema200')
    def test_check_h1_signal_xagusd_none(self, mock_dxy):
        """Verify XAGUSD does not entry if condition is not met."""
        # Condition 1: XAGUSD > EMA200, but DXY > EMA200
        row = {'close': 30.0, 'ema_200': 29.0}
        mock_dxy.return_value = (102.0, 101.0)  # Close > EMA200
        self.assertIsNone(bot.check_h1_signal(row))

        # Condition 2: XAGUSD < EMA200, but DXY < EMA200
        row = {'close': 28.0, 'ema_200': 29.0}
        mock_dxy.return_value = (100.0, 101.0)  # Close < EMA200
        self.assertIsNone(bot.check_h1_signal(row))

    @patch('btc_config.ACTIVE_SYMBOL', 'ETHUSDc')
    @patch('btc_layer_bot.check_timeframe_crossover')
    @patch('btc_layer_bot.open_trade')
    def test_check_and_trigger_entry_ethusd_skips_m1(self, mock_open_trade, mock_cross):
        """Verify check_and_trigger_entry skips M1 crossover logic for ETHUSD."""
        h1_row = {'close': 3000.0, 'ema_200': 2900.0}
        m1_df = pd.DataFrame([{'rsi_14': 50.0}])
        m5_df = pd.DataFrame([{'rsi_14': 50.0}])
        m15_df = pd.DataFrame([{'rsi_14': 50.0}])
        tick = MagicMock(ask=3005.0, bid=2995.0)
        
        # When M15 and M5 crossover do not match but M1 would have matched
        def side_effect(df, tf):
            if tf == "M1":
                return "BUY"
            return None
        mock_cross.side_effect = side_effect
        
        result = bot.check_and_trigger_entry(h1_row, m1_df, m5_df, m15_df, tick)
        self.assertIsNone(result)
        mock_open_trade.assert_not_called()

if __name__ == "__main__":
    unittest.main()
