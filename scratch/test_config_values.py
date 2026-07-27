import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import btc_config
btc_config.set_active_symbol("XAUUSDc")

print("ACTIVE_SYMBOL:", btc_config.ACTIVE_SYMBOL)
print("LAYERING_MODE:", btc_config.LAYERING_MODE)
print("LAYERING_STEP_USD:", btc_config.LAYERING_STEP_USD)
print("TAKE_PROFIT_PER_LAYER_USD:", btc_config.TAKE_PROFIT_PER_LAYER_USD)
print("LOT_SIZE:", btc_config.LOT_SIZE)
print("MAX_LAYERS:", btc_config.MAX_LAYERS)
