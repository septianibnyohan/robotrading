import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import btc_config

print("--- Testing default symbol (BTCUSDc) ---")
print(f"SYMBOL: {btc_config.SYMBOL}")
print(f"LOT_SIZE: {btc_config.LOT_SIZE}")
print(f"MAGIC_NUMBER: {btc_config.MAGIC_NUMBER}")

print("\n--- Switching to XAUUSDc ---")
btc_config.set_active_symbol("XAUUSDc")
print(f"SYMBOL: {btc_config.SYMBOL}")
print(f"LOT_SIZE: {btc_config.LOT_SIZE}")
print(f"MAGIC_NUMBER: {btc_config.MAGIC_NUMBER}")
print(f"MAX_SPREAD_USD: {btc_config.MAX_SPREAD_USD}")

print("\n--- Switching back to BTCUSDc ---")
btc_config.set_active_symbol("BTCUSDc")
print(f"SYMBOL: {btc_config.SYMBOL}")
print(f"LOT_SIZE: {btc_config.LOT_SIZE}")
