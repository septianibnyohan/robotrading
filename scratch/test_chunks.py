import MetaTrader5 as mt5

if mt5.initialize():
    symbol = "BTCUSDc"
    mt5.symbol_select(symbol, True)
    
    # Try copying from position 150,000
    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M1, 150000, 1000)
    if rates is not None:
        print(f"Successfully copied {len(rates)} M1 bars starting at index 150000!")
        print("First bar time:", rates[0][0])
    else:
        print("Failed to copy. Error:", mt5.last_error())
    mt5.shutdown()
else:
    print("Failed to initialize.")
