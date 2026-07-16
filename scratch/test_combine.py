import MetaTrader5 as mt5

if mt5.initialize():
    symbol = "BTCUSDc"
    mt5.symbol_select(symbol, True)
    
    r1 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M1, 0, 50000)
    r2 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M1, 50000, 49000)
    
    if r1 is not None and r2 is not None:
        print(f"Succeeded! Chunk 1: {len(r1)}, Chunk 2: {len(r2)}. Total combined: {len(r1) + len(r2)}")
        print("Chunk 1 start time:", r1[0][0])
        print("Chunk 2 end time:", r2[-1][0])
    else:
        print("Failed to copy chunks.")
    mt5.shutdown()
else:
    print("Failed to initialize.")
