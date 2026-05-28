import sys
import os
import unittest
from unittest.mock import patch, MagicMock

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.telegram import TelegramNotifier
from config.credentials import get_telegram_config

class TestTelegramNotifier(unittest.TestCase):
    
    @patch('config.credentials.os.getenv')
    def test_get_telegram_config(self, mock_getenv):
        """Test retrieving Telegram config from env variables."""
        def side_effect(key, default=None):
            if key == "TELEGRAM_BOT_TOKEN":
                return "test_token"
            elif key == "TELEGRAM_CHAT_ID":
                return "test_chat"
            return default
        mock_getenv.side_effect = side_effect
        
        config = get_telegram_config()
        self.assertEqual(config["bot_token"], "test_token")
        self.assertEqual(config["chat_id"], "test_chat")

    @patch('utils.telegram.requests.get')
    def test_get_latest_chat_id_success(self, mock_get):
        """Test resolving chat ID successfully from bot updates."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "ok": True,
            "result": [
                {
                    "update_id": 12345,
                    "message": {
                        "chat": {
                            "id": 987654321
                        }
                    }
                }
            ]
        }
        mock_get.return_value = mock_response
        
        notifier = TelegramNotifier(bot_token="dummy_token")
        resolved_id = notifier.get_latest_chat_id()
        self.assertEqual(resolved_id, "987654321")

    @patch('utils.telegram.requests.get')
    def test_get_latest_chat_id_empty(self, mock_get):
        """Test resolving chat ID when updates are empty."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "ok": True,
            "result": []
        }
        mock_get.return_value = mock_response
        
        notifier = TelegramNotifier(bot_token="dummy_token")
        resolved_id = notifier.get_latest_chat_id()
        self.assertIsNone(resolved_id)

    @patch('utils.telegram.requests.post')
    def test_send_message_with_chat_id(self, mock_post):
        """Test sending message with pre-configured chat ID."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"ok": True}
        mock_post.return_value = mock_response
        
        notifier = TelegramNotifier(bot_token="dummy_token", chat_id="12345")
        success = notifier.send_message("Hello World", async_send=False)
        
        self.assertTrue(success)
        mock_post.assert_called_once()
        payload = mock_post.call_args[1]["json"]
        self.assertEqual(payload["chat_id"], "12345")
        self.assertEqual(payload["text"], "Hello World")

    @patch('utils.telegram.TelegramNotifier.get_latest_chat_id')
    @patch('utils.telegram.requests.post')
    def test_send_message_dynamic_chat_id(self, mock_post, mock_get_chat_id):
        """Test sending message resolves chat ID dynamically if empty."""
        mock_get_chat_id.return_value = "55555"
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"ok": True}
        mock_post.return_value = mock_response
        
        notifier = TelegramNotifier(bot_token="dummy_token", chat_id="")
        success = notifier.send_message("Testing Dynamic", async_send=False)
        
        self.assertTrue(success)
        self.assertEqual(notifier.chat_id, "6247242674")
        mock_post.assert_called_once()
        payload = mock_post.call_args[1]["json"]
        self.assertEqual(payload["chat_id"], "6247242674")

    @patch('utils.telegram.requests.post')
    def test_send_message_exception_safety(self, mock_post):
        """Test that network exceptions are caught and don't bubble up."""
        mock_post.side_effect = Exception("Connection Timeout")
        
        notifier = TelegramNotifier(bot_token="dummy_token", chat_id="12345")
        try:
            success = notifier.send_message("Will fail but not crash", async_send=False)
            self.assertFalse(success)
        except Exception as e:
            self.fail(f"TelegramNotifier leaked exception: {e}")

    @patch('utils.telegram.requests.post')
    def test_send_message_async(self, mock_post):
        """Test that send_message with async_send=True returns immediately and runs in background."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"ok": True}
        mock_post.return_value = mock_response
        
        notifier = TelegramNotifier(bot_token="dummy_token", chat_id="12345")
        success = notifier.send_message("Hello Async", async_send=True)
        
        self.assertTrue(success)
        # Wait up to 1 second for the background thread to run mock_post
        import time
        for _ in range(10):
            if mock_post.called:
                break
            time.sleep(0.1)
            
        mock_post.assert_called_once()
        payload = mock_post.call_args[1]["json"]
        self.assertEqual(payload["chat_id"], "12345")
        self.assertEqual(payload["text"], "Hello Async")

if __name__ == "__main__":
    unittest.main()
