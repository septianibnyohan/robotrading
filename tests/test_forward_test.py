import os
import sqlite3
import unittest
from unittest.mock import MagicMock, patch
import tempfile
import sys

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.simulator import ForwardTestManager, patch_all
import MetaTrader5 as mt5

class TestForwardTestSimulator(unittest.TestCase):
    def setUp(self):
        # Create a temporary file for the database
        self.db_fd, self.db_path = tempfile.mkstemp(suffix=".sqlite")
        self.initial_balance = 10000.0
        self.manager = ForwardTestManager(db_path=self.db_path, initial_balance=self.initial_balance)

    def tearDown(self):
        # Release references to manager to let SQLite close its connections
        self.manager = None
        import gc
        gc.collect()
        try:
            os.close(self.db_fd)
        except OSError:
            pass
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except Exception as e:
                print(f"Warning: could not clean up temp file: {e}")

    def test_database_initialization(self):
        """Verify tables are correctly created in SQLite database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [t[0] for t in cursor.fetchall()]
        
        self.assertIn("simulated_positions", tables)
        self.assertIn("simulated_deals", tables)
        self.assertIn("simulated_account", tables)
        
        cursor.execute("SELECT value FROM simulated_account WHERE key='balance'")
        balance = cursor.fetchone()[0]
        self.assertEqual(float(balance), self.initial_balance)
        conn.close()

    @patch('MetaTrader5.symbol_info_tick')
    def test_open_trade(self, mock_tick):
        """Verify that opening a trade correctly creates a SimulatedPosition and logs it."""
        mock_tick.return_value = MagicMock(ask=100.0, bid=99.5)
        
        ticket = self.manager.open_trade(
            direction="BUY",
            entry_price=100.0,
            sl_price=95.0,
            tp_price=110.0,
            symbol="BTCUSDc",
            magic=12345
        )
        
        self.assertGreaterEqual(ticket, 100000)
        self.assertEqual(len(self.manager.positions), 1)
        
        pos = self.manager.positions[0]
        self.assertEqual(pos.ticket, ticket)
        self.assertEqual(pos.symbol, "BTCUSDc")
        self.assertEqual(pos.type, 0)  # BUY
        self.assertEqual(pos.price_open, 100.0)
        self.assertEqual(pos.magic, 12345)
        
        # Verify it was written to SQLite
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT ticket, symbol, type, price_open FROM simulated_positions WHERE ticket = ?", (ticket,))
        row = cursor.fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row[0], ticket)
        self.assertEqual(row[1], "BTCUSDc")
        self.assertEqual(row[2], 0)
        self.assertEqual(row[3], 100.0)
        conn.close()

    @patch('MetaTrader5.symbol_info_tick')
    def test_positions_get_and_profit_update(self, mock_tick):
        """Verify that positions_get updates floating profits based on tick pricing."""
        # BUY trade opened at 100.0
        self.manager.open_trade(
            direction="BUY",
            entry_price=100.0,
            sl_price=0.0,
            tp_price=0.0,
            symbol="BTCUSDc",
            magic=12345
        )
        
        # Mock tick price jumps to bid=105.0, ask=106.0
        mock_tick.return_value = MagicMock(bid=105.0, ask=106.0)
        
        positions = self.manager.positions_get(symbol="BTCUSDc")
        self.assertEqual(len(positions), 1)
        
        pos = positions[0]
        # Contract size for BTCUSDc is 1.0. Profit = (105.0 - 100.0) * volume (e.g. 0.01) * 1.0 = 0.05
        # Let's verify formula calculation. Volume is loaded from btc_config.LOT_SIZE, which defaults to 0.01 or similar.
        expected_profit = (105.0 - 100.0) * (pos.volume * 100 * 1.0)
        self.assertAlmostEqual(pos.profit, expected_profit)

    @patch('MetaTrader5.symbol_info_tick')
    def test_close_positions(self, mock_tick):
        """Verify that closing a position updates balance and records a deal."""
        mock_tick.return_value = MagicMock(ask=100.0, bid=102.0)  # bid=102.0 at exit
        
        self.manager.open_trade(
            direction="BUY",
            entry_price=100.0,
            sl_price=0.0,
            tp_price=0.0,
            symbol="BTCUSDc",
            magic=12345
        )
        
        # Close positions
        self.manager.close_all_open_positions(reason="BASKET_TP", symbol="BTCUSDc", magic=12345)
        
        self.assertEqual(len(self.manager.positions), 0)
        
        # Verify database position table is empty
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM simulated_positions")
        self.assertEqual(cursor.fetchone()[0], 0)
        
        # Verify balance updated
        # profit = (102.0 - 100.0) * volume * 1.0 = 2.0 * volume. Spread deduction = SPREAD_DEDUCTION_USD * volume * 1.0.
        import btc_config
        volume = 0.01  # default fallback volume
        if len(self.manager.history_deals_get(0)) > 0:
            volume = self.manager.history_deals_get(0)[-1].volume
            
        profit = (102.0 - 100.0) * (volume * 100 * 1.0)
        spread_deduction = btc_config.SPREAD_DEDUCTION_USD * volume * 1.0
        expected_net_profit = profit - spread_deduction
        
        self.assertAlmostEqual(self.manager.balance, self.initial_balance + expected_net_profit)
        
        # Verify deals table contains the entry and close deals
        cursor.execute("SELECT entry, profit FROM simulated_deals ORDER BY id ASC")
        deals = cursor.fetchall()
        self.assertEqual(len(deals), 2)
        self.assertEqual(deals[0][0], 0)  # DEAL_ENTRY_IN
        self.assertEqual(deals[0][1], 0.0)
        self.assertEqual(deals[1][0], 1)  # DEAL_ENTRY_OUT
        self.assertAlmostEqual(deals[1][1], expected_net_profit)
        
        conn.close()

    def test_state_persistence_on_restart(self):
        """Verify simulated state can be reloaded in a new manager instance."""
        # Create a position manually in DB
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO simulated_positions (ticket, symbol, type, volume, price_open, magic, sl, tp, time)
            VALUES (999, 'BTCUSDc', 0, 0.1, 99.0, 5555, 0.0, 0.0, 1234567)
        """)
        cursor.execute("UPDATE simulated_account SET value = 8500.5 WHERE key = 'balance'")
        conn.commit()
        conn.close()
        
        # Re-instantiate manager
        new_manager = ForwardTestManager(db_path=self.db_path, initial_balance=10000.0)
        self.assertEqual(new_manager.balance, 8500.5)
        self.assertEqual(len(new_manager.positions), 1)
        
        pos = new_manager.positions[0]
        self.assertEqual(pos.ticket, 999)
        self.assertEqual(pos.symbol, "BTCUSDc")
        self.assertEqual(pos.volume, 0.1)
        self.assertEqual(pos.price_open, 99.0)
        self.assertEqual(pos.magic, 5555)

    def test_monkeypatching(self):
        """Verify that patch_all successfully binds simulated methods to target modules."""
        orig_positions_get = mt5.positions_get
        orig_history_deals_get = mt5.history_deals_get
        orig_account_info = mt5.account_info
        
        import btc_trading
        orig_open_trade = btc_trading.open_trade
        orig_close_all_open_positions = btc_trading.close_all_open_positions
        
        # Create a mock main/bot module to test namespace patching
        import types
        mock_main = types.ModuleType("__main__")
        mock_main.open_trade = lambda: None
        mock_main.close_all_open_positions = lambda: None
        
        mock_bot = types.ModuleType("btc_layer_bot")
        mock_bot.open_trade = lambda: None
        mock_bot.close_all_open_positions = lambda: None
        
        orig_main = sys.modules.get('__main__')
        orig_bot = sys.modules.get('btc_layer_bot')
        
        sys.modules['__main__'] = mock_main
        sys.modules['btc_layer_bot'] = mock_bot
        
        try:
            patch_all(self.manager)
            
            # Check MetaTrader5 functions
            self.assertEqual(mt5.positions_get, self.manager.positions_get)
            self.assertEqual(mt5.history_deals_get, self.manager.history_deals_get)
            self.assertEqual(mt5.account_info, self.manager.account_info)
            
            # Check btc_trading functions
            self.assertEqual(btc_trading.open_trade, self.manager.open_trade)
            self.assertEqual(btc_trading.close_all_open_positions, self.manager.close_all_open_positions)
            
            # Check target module namespace functions
            self.assertEqual(mock_main.open_trade, self.manager.open_trade)
            self.assertEqual(mock_main.close_all_open_positions, self.manager.close_all_open_positions)
            self.assertEqual(mock_bot.open_trade, self.manager.open_trade)
            self.assertEqual(mock_bot.close_all_open_positions, self.manager.close_all_open_positions)
        finally:
            # Restore originals
            mt5.positions_get = orig_positions_get
            mt5.history_deals_get = orig_history_deals_get
            mt5.account_info = orig_account_info
            
            btc_trading.open_trade = orig_open_trade
            btc_trading.close_all_open_positions = orig_close_all_open_positions
            
            if orig_main:
                sys.modules['__main__'] = orig_main
            if orig_bot:
                sys.modules['btc_layer_bot'] = orig_bot

if __name__ == "__main__":
    unittest.main()
