import MetaTrader5 as mt5
from datetime import datetime, timezone

if mt5.initialize():
    symbol = "BTCUSDc"
    mt5.symbol_select(symbol, True)
    
    # 2 years ago
    utc_to = datetime.now(timezone.utc)
    utc_from = datetime(2024, 7, 11, tzinfo=timezone.utc)
    
    rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M1, utc_from, utc_to)
    if rates is not None:
        print(f"Successfully copied {len(rates)} M1 bars for 2 years!")
    else:
        print("Failed to copy. Error:", mt5.last_error())
    mt5.shutdown()
else:
    print("Failed to initialize.")
