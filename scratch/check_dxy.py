import MetaTrader5 as mt5
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.mt5_bridge import MT5Bridge

def main():
    bridge = MT5Bridge()
    if not bridge.connect():
        print("Failed to connect to MT5")
        return

    print("Checking MT5 symbols...")
    symbols = mt5.symbols_get()
    if not symbols:
        print("No symbols retrieved")
        mt5.shutdown()
        return

    print(f"Total symbols: {len(symbols)}")
    for i, s in enumerate(symbols):
        print(f"{i+1}: {s.name}")

    mt5.shutdown()

if __name__ == "__main__":
    main()
