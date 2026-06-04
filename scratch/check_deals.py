import MetaTrader5 as mt5
import sys
from datetime import datetime, timezone, timedelta

if not mt5.initialize():
    print("MT5 initialization failed")
    sys.exit(1)

now = datetime.now(timezone.utc)
start = now - timedelta(days=7)

deals = mt5.history_deals_get(start, now + timedelta(seconds=10))
if deals is None:
    print("Failed to get deals history")
elif len(deals) == 0:
    print("No deals found in the last 7 days.")
else:
    print(f"Deals with volume 0.03 or similar in the last 7 days:")
    found = False
    for d in deals:
        if abs(d.volume - 0.03) < 0.001 or d.volume > 0.01:
            found = True
            deal_time = datetime.fromtimestamp(d.time, tz=timezone.utc)
            print(f"Time: {deal_time} | Ticket: {d.ticket} | Symbol: {d.symbol} | "
                  f"Type: {'BUY' if d.type == mt5.DEAL_TYPE_BUY else 'SELL'} | Entry: {d.entry} | "
                  f"Volume: {d.volume} | Price: {d.price} | Profit: {d.profit} | Magic: {d.magic} | Comment: {d.comment}")
    if not found:
        print("No deals found with volume > 0.01 or 0.03.")

mt5.shutdown()
