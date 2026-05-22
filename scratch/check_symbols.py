import MetaTrader5 as mt5
from dotenv import load_dotenv
import os

load_dotenv()

if not mt5.initialize():
    print("initialize() failed, error code =", mt5.last_error())
    quit()

symbols = mt5.symbols_get()
for s in symbols:
    if "XAU" in s.name or "NAS" in s.name or "USTEC" in s.name:
        print(s.name)

mt5.shutdown()
