SYMBOL = "ETHUSDc"
MAGIC_NUMBER = 20260801
MAGIC_NUMBER_M5 = 20260802
MAGIC_NUMBER_M15 = 20260803


# Late-Night Window (00:00 - 02:59 WIB): Max layers encountered: 22 (excluding Wednesday session).
# min 14, med: 33, max: 129
LOT_SIZE = 0.1 * (3)
MAX_SPREAD_USD = 1.5
SPREAD_DEDUCTION_USD = 1.00
MAX_CONCURRENT_POSITIONS = 1

EMA_FAST, EMA_MED, EMA_SLOW = 9, 21, 200
H1_EMA_PERIOD, RSI_PERIOD, ATR_PERIOD = 50, 14, 14
ADX_PERIOD, VOL_EMA_PERIOD = 14, 10
RSI_PERIOD_M1, RSI_LIMIT_UP_M1, RSI_LIMIT_DOWN_M1 = 7, 80, 20


# Layering Strategy Config
LAYERING_MODE = "USD"  # "USD" or "ATR"
LAYERING_STEP_ATR_MULT = 1.0 * (3) # Late-Night Window (23:00 - 03:00 WIB): Max layers reached was 14.
LAYERING_STEP_USD = 10.0
TAKE_PROFIT_PER_LAYER_USD = (0.2) * (3)
MAX_LAYERS = None  # None for unlimited
EXIT_LOGIC_AND = True  # True: both RSI & close conditions; False: either condition
number_of_normal_layer = 200
constant = 2

# Times to Avoid: 20:00 WIB (max layers 218), 03:00 WIB (max layers 73), 11:00 WIB (max layers 68), and 23:00 WIB (max layers 33).
# 1 - 2
LOW_RISK_OVERRIDES = {
    "LOT_SIZE": 0.1 * (25), # sunday (1), 3, other max(12)
    "LAYERING_STEP_ATR_MULT": 1.0 * 1,
    "TAKE_PROFIT_PER_LAYER_USD": 0.2 * (25), #1
}

# Morning Window (05:00 - 10:59 WIB): Max layers encountered: 21 (excluding Wednesday session).
# min 11, mid: 25,  max:100,
MODERATE_RISK_OVERRIDES = {
    "LOT_SIZE": 0.1 * (4), # Asian Session Window (07:00 - 15:00 WIB): Max layers reached was 24
    "LAYERING_STEP_ATR_MULT": 1.0 * 1,
    "TAKE_PROFIT_PER_LAYER_USD": 0.2 * (4), #25 - 100
}
