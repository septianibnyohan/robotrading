import MetaTrader5 as mt5
import sys
from datetime import datetime, timezone, timedelta

if not mt5.initialize():
    print("MT5 initialization failed")
    sys.exit(1)

now = datetime.now(timezone.utc)
start = now - timedelta(days=3)

deals = mt5.history_deals_get(start, now + timedelta(seconds=10))
if deals is None:
    print("Failed to get deals history")
elif len(deals) == 0:
    print("No deals found in the last 3 days.")
else:
    print(f"Deals of size 0.03 in the last 3 days:")
    count = 0
    for d in deals:
        if abs(d.volume - 0.03) < 0.001:
            count += 1
            deal_time = datetime.fromtimestamp(d.time, tz=timezone.utc)
            print(f"Time (UTC): {deal_time} | Ticket: {d.ticket} | Order: {d.order} | Symbol: {d.symbol} | "
                  f"Type: {'BUY' if d.type == mt5.DEAL_TYPE_BUY else 'SELL'} | Entry: {d.entry} | "
                  f"Volume: {d.volume} | Price: {d.price} | Profit: {d.profit} | Magic: {d.magic} | Comment: {d.comment}")
    if count == 0:
         print("No deals found with volume 0.03.")

mt5.shutdown()
