import MetaTrader5 as mt5

if mt5.initialize():
    symbol = "BTCUSDc"
    mt5.symbol_select(symbol, True)
    for limit in [1000, 5000, 10000, 50000, 100000]:
        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M1, 0, limit)
        if rates is not None:
            print(f"Limit {limit}: copied {len(rates)} bars.")
        else:
            print(f"Limit {limit}: failed. Error:", mt5.last_error())
    mt5.shutdown()
else:
    print("Failed to initialize.")
