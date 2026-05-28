import logging
import threading
import requests
from config.credentials import get_telegram_config

logger = logging.getLogger(__name__)

class TelegramNotifier:
    """
    Utility class to send alerts/notifications to Telegram.
    Includes automatic chat ID discovery via /getUpdates.
    """
    
    def __init__(self, bot_token: str = None, chat_id: str = None):
        config = get_telegram_config()
        self.bot_token = bot_token or config.get("bot_token", "")
        self.chat_id = chat_id or config.get("chat_id", "")
        
        if not self.bot_token:
            logger.warning("[TELEGRAM] No bot token configured. Alerts will be disabled.")

    def get_latest_chat_id(self) -> str:
        """
        Queries Telegram /getUpdates API to automatically resolve the chat ID
        of the most recent user interaction.
        """
        if not self.bot_token:
            logger.error("[TELEGRAM] Cannot resolve chat ID: Bot token is missing.")
            return None
            
        url = f"https://api.telegram.org/bot{self.bot_token}/getUpdates"
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get("ok"):
                    results = data.get("result", [])
                    # Traverse results backward to get the latest interaction
                    for update in reversed(results):
                        # Message object can be under 'message', 'edited_message', etc.
                        msg_obj = update.get("message") or update.get("edited_message")
                        if msg_obj and "chat" in msg_obj:
                            resolved_id = str(msg_obj["chat"]["id"])
                            logger.info(f"[TELEGRAM] Automatically resolved chat ID: {resolved_id}")
                            return resolved_id
                    logger.warning("[TELEGRAM] /getUpdates returned no active chat/message history. Please send a message to the bot first.")
                else:
                    logger.error(f"[TELEGRAM] /getUpdates failed: {data.get('description')}")
            else:
                logger.error(f"[TELEGRAM] /getUpdates failed with status code {response.status_code}")
        except Exception as e:
            logger.error(f"[TELEGRAM] Error calling getUpdates: {e}")
            
        return None

    def send_message(self, text: str, async_send: bool = True) -> bool:
        """
        Sends a message to the configured Telegram chat.
        If async_send is True, it spawns a background thread and returns True immediately.
        Otherwise, it runs synchronously.
        """
        if not self.bot_token:
            return False

        if async_send:
            thread = threading.Thread(target=self._send_message_sync, args=(text,), daemon=True)
            thread.start()
            return True
        else:
            return self._send_message_sync(text)

    def _send_message_sync(self, text: str) -> bool:
        """
        Internal synchronous method to send the Telegram message.
        """
        # Try resolving chat_id dynamically if empty
        if not self.chat_id:
            logger.info("[TELEGRAM] Chat ID is not configured. Attempting to resolve chat ID from latest bot updates...")
            self.chat_id = self.get_latest_chat_id()
            if not self.chat_id:
                logger.error("[TELEGRAM] Message could not be sent: Chat ID could not be resolved.")
                return False
                
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "HTML"
        }
        
        try:
            response = requests.post(url, json=payload, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get("ok"):
                    logger.debug("[TELEGRAM] Alert sent successfully.")
                    return True
                else:
                    logger.error(f"[TELEGRAM] Send message failed: {data.get('description')}")
            else:
                logger.error(f"[TELEGRAM] Send message failed with status code {response.status_code}: {response.text}")
        except Exception as e:
            logger.error(f"[TELEGRAM] Exception occurred while sending Telegram alert: {e}")
            
        return False
