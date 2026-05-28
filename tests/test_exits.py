import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import MetaTrader5 as mt5
from execution.executor import TradeExecutor

class TestTradeExecutorExits(unittest.TestCase):
    def setUp(self):
        self.symbol = "XAUUSDc"
        self.executor = TradeExecutor(self.symbol)

    @patch('MetaTrader5.symbol_info_tick')
    @patch('MetaTrader5.order_send')
    def test_close_position_buy(self, mock_order_send, mock_symbol_info_tick):
        """Verify close_position sends a sell request for a BUY position."""
        mock_tick = MagicMock()
        mock_tick.bid = 2000.50
        mock_tick.ask = 2001.00
        mock_symbol_info_tick.return_value = mock_tick

        mock_result = MagicMock()
        mock_result.retcode = mt5.TRADE_RETCODE_DONE
        mock_order_send.return_value = mock_result

        # Create a mock BUY position
        mock_pos = MagicMock()
        mock_pos.ticket = 12345
        mock_pos.volume = 0.1
        mock_pos.type = mt5.POSITION_TYPE_BUY

        res = self.executor.close_position(mock_pos)

        self.assertIsNotNone(res)
        mock_order_send.assert_called_once()
        sent_request = mock_order_send.call_args[0][0]
        
        self.assertEqual(sent_request["action"], mt5.TRADE_ACTION_DEAL)
        self.assertEqual(sent_request["symbol"], self.symbol)
        self.assertEqual(sent_request["volume"], 0.1)
        self.assertEqual(sent_request["type"], mt5.ORDER_TYPE_SELL)
        self.assertEqual(sent_request["position"], 12345)
        self.assertEqual(sent_request["price"], 2000.50)

    @patch('MetaTrader5.symbol_info_tick')
    @patch('MetaTrader5.order_send')
    def test_close_position_sell(self, mock_order_send, mock_symbol_info_tick):
        """Verify close_position sends a buy request for a SELL position."""
        mock_tick = MagicMock()
        mock_tick.bid = 2000.50
        mock_tick.ask = 2001.00
        mock_symbol_info_tick.return_value = mock_tick

        mock_result = MagicMock()
        mock_result.retcode = mt5.TRADE_RETCODE_DONE
        mock_order_send.return_value = mock_result

        # Create a mock SELL position
        mock_pos = MagicMock()
        mock_pos.ticket = 54321
        mock_pos.volume = 0.2
        mock_pos.type = mt5.POSITION_TYPE_SELL

        res = self.executor.close_position(mock_pos)

        self.assertIsNotNone(res)
        mock_order_send.assert_called_once()
        sent_request = mock_order_send.call_args[0][0]
        
        self.assertEqual(sent_request["action"], mt5.TRADE_ACTION_DEAL)
        self.assertEqual(sent_request["symbol"], self.symbol)
        self.assertEqual(sent_request["volume"], 0.2)
        self.assertEqual(sent_request["type"], mt5.ORDER_TYPE_BUY)
        self.assertEqual(sent_request["position"], 54321)
        self.assertEqual(sent_request["price"], 2001.00)

    @patch('execution.executor.TradeExecutor.close_position')
    @patch('execution.executor.TradeExecutor.get_open_positions')
    def test_close_all_positions(self, mock_get_open_positions, mock_close_position):
        """Verify close_all_positions calls close_position for each open position."""
        mock_pos1 = MagicMock()
        mock_pos2 = MagicMock()
        mock_get_open_positions.return_value = [mock_pos1, mock_pos2]

        self.executor.close_all_positions()

        mock_get_open_positions.assert_called_once()
        self.assertEqual(mock_close_position.call_count, 2)
        mock_close_position.assert_any_call(mock_pos1)
        mock_close_position.assert_any_call(mock_pos2)

if __name__ == "__main__":
    unittest.main()
