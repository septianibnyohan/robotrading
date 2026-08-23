import os
from dotenv import load_dotenv

load_dotenv()

def get_mt5_credentials():
    """
    Retrieves MT5 credentials from environment variables.
    """
    return {
        "login": int(os.getenv("EXNESS_LOGIN", 0)),
        "password": os.getenv("EXNESS_PASSWORD", ""),
        "server": os.getenv("EXNESS_SERVER", ""),
        "symbol": os.getenv("EXNESS_SYMBOL", "BTCUSDc,XAUUSDc,XAGUSDc,ETHUSDc,EURUSDc,EURJPYc,ETHUSDm,EURUSDm,EURJPYm,USDJPYm"),
    }

def get_telegram_config():
    """
    Retrieves Telegram configuration from environment variables.
    """
    return {
        "bot_token": os.getenv("TELEGRAM_BOT_TOKEN", ""),
        "chat_id": os.getenv("TELEGRAM_CHAT_ID", ""),
    }

