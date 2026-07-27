SYMBOL = "XAUUSDc"
MAGIC_NUMBER = 20260606
MAGIC_NUMBER_M5 = 20260607

# Late-Night Window (01:00 - 05:00 WIB): Max layers encountered: 17.
# min 10, max = 39
LOT_SIZE = 0.01 * 10
MAX_SPREAD_USD = 2.5
SPREAD_DEDUCTION_USD = 0.36
MAX_CONCURRENT_POSITIONS = 1

EMA_FAST, EMA_MED, EMA_SLOW = 5, 21, 200
H1_EMA_PERIOD, RSI_PERIOD, ATR_PERIOD = 50, 7, 14
ADX_PERIOD, VOL_EMA_PERIOD = 14, 10
RSI_PERIOD_M1, RSI_LIMIT_UP_M1, RSI_LIMIT_DOWN_M1 = 7, 80, 20


# Layering Strategy Config
LAYERING_MODE = "USD"  # "USD" or "ATR"
LAYERING_STEP_ATR_MULT = 5.0
LAYERING_STEP_USD = 5.0
TAKE_PROFIT_PER_LAYER_USD = 1.0 * 10
MAX_LAYERS = None  # None for unlimited
EXIT_LOGIC_AND = True  # True: both RSI & close conditions; False: either condition
number_of_normal_layer = 1000
constant = 2

# Low risk overrides (used outside peak hours on weekdays)
# Times to Avoid: 14:00 WIB (max layers 88), 19:00 WIB (max layers 85), 10:00 WIB (max layers 50), 21:00 WIB (max layers 45), and 05:00 WIB (max layers 43).
# min 0.01/77.880, max 0.01 lot/19.580
LOW_RISK_OVERRIDES = {
    "LOT_SIZE": 0.01 * 1,
    "LAYERING_STEP_ATR_MULT": 5.0,
    "TAKE_PROFIT_PER_LAYER_USD": 1.0 * 1,
}

# Moderate risk overrides
# Overnight Window (22:00 - 04:00 WIB): Max layers encountered: 26.
# min 4, max = 17
MODERATE_RISK_OVERRIDES = {
    "LOT_SIZE": 0.01 * 4,
    "LAYERING_STEP_ATR_MULT": 5.0,
    "TAKE_PROFIT_PER_LAYER_USD": 1.0 * 4,
}
