import MetaTrader5 as mt5

if not mt5.initialize():
    print(f"Failed to initialize: {mt5.last_error()}")
    exit(1)

# List all symbols with XAU or USD
symbols = mt5.symbols_get()
for s in symbols:
    if "XAU" in s.name:
        print(f"Found symbol: {s.name}, select: {s.select}")
        # Get more info
        info = mt5.symbol_info(s.name)
        if info:
            print(f"  Bid: {info.bid}, Ask: {info.ask}, Digits: {info.digits}, Point: {info.point}")
mt5.shutdown()
