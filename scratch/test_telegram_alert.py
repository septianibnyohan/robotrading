import sys
import os
import logging

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.telegram import TelegramNotifier

# Setup simple logging to stdout
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def main():
    print("Initializing TelegramNotifier...")
    notifier = TelegramNotifier()
    
    print("\n--- Current Configuration ---")
    print(f"Bot Token: {notifier.bot_token[:15]}... (length: {len(notifier.bot_token) if notifier.bot_token else 0})")
    print(f"Configured Chat ID: {notifier.chat_id}")
    print("-----------------------------\n")
    
    if not notifier.chat_id:
        print("Chat ID is empty. Attempting dynamic resolution from /getUpdates...")
        print("NOTE: Make sure you have started a chat with the bot by sending it a message first!")
        resolved_chat_id = notifier.get_latest_chat_id()
        if resolved_chat_id:
            print(f"\n[OK] Successfully resolved Chat ID: {resolved_chat_id}")
            print(f"Please add this chat ID to your .env file as:")
            print(f"TELEGRAM_CHAT_ID={resolved_chat_id}")
            # Assign resolved chat ID to test sending message
            notifier.chat_id = resolved_chat_id
        else:
            print("\n[ERROR] Failed to resolve Chat ID automatically.")
            print("Please ensure you have sent at least one message (like '/start') to the bot on Telegram.")
            return

    test_message = (
        "<b>[RoboBTC Test Alert]</b>\n"
        "This is a test notification verifying the Telegram integration.\n\n"
        "• <b>EMA Fast:</b> 2012.34\n"
        "• <b>EMA Slow:</b> 2010.56\n"
        "• <b>RSI Previous:</b> 48.75\n"
        "• <b>RSI Current:</b> 52.10\n"
        "<i>Crossover event successfully verified!</i>"
    )
    
    print("\nSending test message...")
    success = notifier.send_message(test_message)
    if success:
        print("\n[OK] Test message sent successfully! Please check your Telegram app.")
    else:
        print("\n[ERROR] Failed to send test message. Check logs/exceptions above.")

if __name__ == "__main__":
    main()
