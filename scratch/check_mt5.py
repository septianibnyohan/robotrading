import MetaTrader5 as mt5
import sys

if not mt5.initialize():
    print(f"Failed to initialize MT5: {mt5.last_error()}")
    sys.exit(1)

print("MT5 initialized successfully!")
terminal_info = mt5.terminal_info()
print("Terminal Info:", terminal_info)

# Check symbols
symbols = mt5.symbols_get()
print(f"Total symbols: {len(symbols)}")
for s in symbols[:20]:
    print(f"Symbol: {s.name}")

mt5.shutdown()
