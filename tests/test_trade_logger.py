import unittest
from unittest.mock import patch, MagicMock
import os
import sqlite3
import numpy as np

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.trade_logger import TradeRsiLogger

class TestTradeRsiLogger(unittest.TestCase):
    def setUp(self):
        self.db_path = "data/database/test_trade_rsi_log.sqlite"
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
            
    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    @patch('MetaTrader5.copy_rates_from_pos')
    def test_calculate_rsi(self, mock_copy_rates):
        np.random.seed(42)
        closes = [100.0]
        for _ in range(149):
            closes.append(closes[-1] + np.random.choice([-1.0, 1.0]))
            
        mock_rates = []
        for i, close in enumerate(closes):
            mock_rates.append((
                1700000000 + i * 60,
                close - 0.5,
                close + 1.0,
                close - 1.0,
                close,
                100,
                1,
                0
            ))
            
        dtype = [('time', 'i8'), ('open', 'f8'), ('high', 'f8'), ('low', 'f8'), ('close', 'f8'), 
                 ('tick_volume', 'i8'), ('spread', 'i8'), ('real_volume', 'i8')]
        rates_array = np.array(mock_rates, dtype=dtype)
        mock_copy_rates.return_value = rates_array
        
        logger_inst = TradeRsiLogger(db_path=self.db_path)
        rsi_val = logger_inst._calculate_rsi("BTCUSD", 1)
        
        self.assertTrue(0 <= rsi_val <= 100)
        mock_copy_rates.assert_called_with("BTCUSD", 1, 0, 150)

    @patch('MetaTrader5.copy_rates_from_pos')
    def test_log_trade(self, mock_copy_rates):
        dtype = [('time', 'i8'), ('open', 'f8'), ('high', 'f8'), ('low', 'f8'), ('close', 'f8'), 
                 ('tick_volume', 'i8'), ('spread', 'i8'), ('real_volume', 'i8')]
        mock_rates = [(1700000000 + i, 10.0, 12.0, 9.0, 10.0 + i, 10, 1, 0) for i in range(150)]
        rates_array = np.array(mock_rates, dtype=dtype)
        mock_copy_rates.return_value = rates_array
        
        logger_inst = TradeRsiLogger(db_path=self.db_path)
        logger_inst.log_trade(
            ticket=999888,
            action="CLOSED",
            symbol="XAUUSD",
            price=2050.25,
            volume=0.05,
            profit=25.50
        )
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM trade_rsi_log")
        rows = cursor.fetchall()
        conn.close()
        
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row[2], 999888)
        self.assertEqual(row[3], "CLOSED")
        self.assertEqual(row[4], "XAUUSD")
        self.assertEqual(row[5], 2050.25)
        self.assertEqual(row[6], 0.05)
        
        # Verify 8 timeframes (M1, M5, M15, M30, H1, H4, D1, W1)
        for idx in range(7, 15):
            self.assertTrue(0 <= row[idx] <= 100)
            
        # Verify profit value
        self.assertEqual(row[15], 25.50)

if __name__ == '__main__':
    unittest.main()
