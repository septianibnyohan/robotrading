import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import btc_config
import datetime

print(f"Current local time: {datetime.datetime.now()}")
print(f"Current hour: {btc_config._get_current_hour()}")
print(f"Active module: {btc_config._get_active_module()}")
print(f"LOT_SIZE: {btc_config.LOT_SIZE}")
print(f"TAKE_PROFIT_PER_LAYER_USD: {btc_config.TAKE_PROFIT_PER_LAYER_USD}")
print(f"LAYERING_STEP_ATR_MULT: {btc_config.LAYERING_STEP_ATR_MULT}")
