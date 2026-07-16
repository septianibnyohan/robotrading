SYMBOL = "XAGUSDc"
MAGIC_NUMBER = 20260610
MAGIC_NUMBER_M5 = 20260611

# Late-Night Window (00:00 - 03:00 WIB): Max layers encountered: 8.
# min = 14, max = 55
LOT_SIZE = 0.01 * 14
MAX_SPREAD_USD = 1000
SPREAD_DEDUCTION_USD = 0.15
MAX_CONCURRENT_POSITIONS = 1

EMA_FAST, EMA_MED, EMA_SLOW = 5, 21, 200
H1_EMA_PERIOD, RSI_PERIOD, ATR_PERIOD = 50, 7, 14
ADX_PERIOD, VOL_EMA_PERIOD = 14, 10
RSI_PERIOD_M1, RSI_LIMIT_UP_M1, RSI_LIMIT_DOWN_M1 = 7, 80, 20


# Layering Strategy Config
LAYERING_MODE = "USD"  # "USD" or "ATR"
LAYERING_STEP_ATR_MULT = 0.300
LAYERING_STEP_USD = 0.300
TAKE_PROFIT_PER_LAYER_USD = 3 * 14
MAX_LAYERS = None  # None for unlimited
EXIT_LOGIC_AND = True  # True: both RSI & close conditions; False: either condition
number_of_normal_layer = 1000
constant = 10

# Low risk overrides (used outside peak hours on weekdays)
# Times to Avoid: 20:00 - 21:00 WIB (US session open; max layers 19), 03:00 WIB (max layers 14), 23:00 WIB (max layers 13), and 17:00 WIB (max layers 12)
# min = 2, max = 10
LOW_RISK_OVERRIDES = {
    "LOT_SIZE": 0.01 * 2,
    "LAYERING_STEP_ATR_MULT": 0.300,
    "TAKE_PROFIT_PER_LAYER_USD": 3 * 2,
}

# Moderate risk overrides
# Morning Window (04:00 - 13:00 WIB): Max layers encountered: 11.
# min = 7, max = 30
MODERATE_RISK_OVERRIDES = {
    "LOT_SIZE": 0.01 * 7,
    "LAYERING_STEP_ATR_MULT": 0.300,
    "TAKE_PROFIT_PER_LAYER_USD": 3 * 7,
}
