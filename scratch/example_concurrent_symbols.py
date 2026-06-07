import sys
import os
import threading
import time

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import btc_config
from btc_trading import close_all_open_positions, open_trade

def run_symbol_bot(symbol_name):
    """
    Simulates a trading bot thread trading a specific symbol.
    """
    # 1. Bind this thread's context to the target symbol
    btc_config.set_active_symbol(symbol_name)
    
    # 2. Retrieve dynamic settings
    print(f"[{symbol_name} Bot] Started. Target Symbol: {btc_config.SYMBOL}")
    print(f"[{symbol_name} Bot] Lot Size: {btc_config.LOT_SIZE} | Magic Number: {btc_config.MAGIC_NUMBER}")
    
    # 3. Simulate processing and querying configuration properties
    for i in range(3):
        # Even if other threads switch active symbol, this thread's settings remain isolated
        time.sleep(0.1)
        print(f"[{symbol_name} Bot] Loop {i+1} - Active Symbol in btc_config: {btc_config.SYMBOL} (Lot: {btc_config.LOT_SIZE})")

    # 4. Symbol-isolated exit check
    print(f"[{symbol_name} Bot] Exiting and closing positions exclusively for {btc_config.SYMBOL}...")
    # This will call close_all_open_positions with the correct context symbol
    close_all_open_positions(reason="Exit Example", symbol=btc_config.SYMBOL)
    print(f"[{symbol_name} Bot] Finished.")

def main():
    print("=== Starting Concurrent Multi-Symbol Config Isolation Example ===\n")
    
    # Create threads for concurrent symbol bots
    thread_btc = threading.Thread(target=run_symbol_bot, args=("BTCUSDc",))
    thread_xau = threading.Thread(target=run_symbol_bot, args=("XAUUSDc",))
    
    # Start threads
    thread_btc.start()
    time.sleep(0.02)  # Slight offset to show staggered initialization
    thread_xau.start()
    
    # Wait for completion
    thread_btc.join()
    thread_xau.join()
    
    print("\n=== Concurrent Multi-Symbol Config Isolation Example Complete ===")

if __name__ == "__main__":
    main()
