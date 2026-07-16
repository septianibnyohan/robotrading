import MetaTrader5 as mt5

print("Initializing MT5...")
if mt5.initialize():
    print("MT5 initialized successfully!")
    print("Terminal Info:", mt5.terminal_info())
    print("Version:", mt5.version())
    symbol = "BTCUSDc"
    selected = mt5.symbol_select(symbol, True)
    print(f"Selecting {symbol}:", selected)
    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M1, 0, 10)
    if rates is not None:
        print(f"Successfully copied {len(rates)} bars.")
    else:
        print("Failed to copy rates. Last error:", mt5.last_error())
    mt5.shutdown()
else:
    print("Failed to initialize MT5. Last error:", mt5.last_error())
