import MetaTrader5 as mt5
import sys

if not mt5.initialize():
    print("MT5 initialization failed")
    sys.exit(1)

positions = mt5.positions_get()
if positions is None:
    print("Failed to get positions")
elif len(positions) == 0:
    print("No open positions found.")
else:
    print(f"Active positions ({len(positions)}):")
    for pos in positions:
        print(f"Ticket: {pos.ticket} | Symbol: {pos.symbol} | Type: {'BUY' if pos.type == mt5.POSITION_TYPE_BUY else 'SELL'} | Volume: {pos.volume} | Price: {pos.price_open} | Profit: {pos.profit} | Magic: {pos.magic}")

account_info = mt5.account_info()
if account_info:
    print(f"\nAccount Balance: {account_info.balance} | Equity: {account_info.equity}")

mt5.shutdown()
