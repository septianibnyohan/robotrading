import unittest
from unittest.mock import MagicMock, patch
import pandas as pd
import sys
import os
from datetime import datetime, timezone

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import check_cooldown

class TestMainCooldown(unittest.TestCase):
    def setUp(self):
        self.logger = MagicMock()
        self.symbol = "XAUUSDc"

    @patch('MetaTrader5.history_deals_get')
    def test_cooldown_inactive_no_deals(self, mock_history):
        """Verify cooldown is false when there are no deals."""
        mock_history.return_value = None
        
        is_active, last_time = check_cooldown(self.symbol, 1, datetime.now(timezone.utc), self.logger)
        self.assertFalse(is_active)
        self.assertIsNone(last_time)

    @patch('MetaTrader5.history_deals_get')
    def test_cooldown_inactive_non_sl_deal(self, mock_history):
        """Verify cooldown is false when last deal is not an SL exit."""
        mock_deal = MagicMock()
        mock_deal.symbol = self.symbol
        mock_deal.entry = 1  # DEAL_ENTRY_OUT
        mock_deal.reason = 1  # DEAL_REASON_CLIENT
        mock_deal.comment = "Take Profit"
        mock_deal.time = int(datetime.now(timezone.utc).timestamp())
        
        mock_history.return_value = [mock_deal]
        
        is_active, last_time = check_cooldown(self.symbol, 1, datetime.now(timezone.utc), self.logger)
        self.assertFalse(is_active)
        self.assertIsNone(last_time)

    @patch('MetaTrader5.history_deals_get')
    def test_cooldown_active_after_sl(self, mock_history):
        """Verify cooldown is active when last deal is an SL exit and within 3 candles."""
        now = datetime.now(timezone.utc)
        mock_deal = MagicMock()
        mock_deal.symbol = self.symbol
        mock_deal.entry = 1  # DEAL_ENTRY_OUT
        mock_deal.reason = 3  # DEAL_REASON_SL
        mock_deal.comment = "sl"
        mock_deal.time = int(now.timestamp()) - 30  # 30 seconds ago
        
        mock_history.return_value = [mock_deal]
        
        # Test current bar is within 3 candles (1-minute timeframe)
        current_bar_time = now
        is_active, last_time = check_cooldown(self.symbol, 1, current_bar_time, self.logger)
        self.assertTrue(is_active)
        self.assertEqual(last_time, mock_deal.time)

    @patch('MetaTrader5.history_deals_get')
    def test_cooldown_expired(self, mock_history):
        """Verify cooldown is expired after 4 candles."""
        now = datetime.now(timezone.utc)
        mock_deal = MagicMock()
        mock_deal.symbol = self.symbol
        mock_deal.entry = 1  # DEAL_ENTRY_OUT
        mock_deal.reason = 3  # DEAL_REASON_SL
        mock_deal.comment = "sl"
        # 5 minutes ago (cooldown expired for 1-minute timeframe)
        mock_deal.time = int(now.timestamp()) - 300
        
        mock_history.return_value = [mock_deal]
        
        is_active, last_time = check_cooldown(self.symbol, 1, now, self.logger)
        self.assertFalse(is_active)

if __name__ == "__main__":
    unittest.main()
