SYMBOL = "XAGUSDc"
MAGIC_NUMBER = 20260610
MAGIC_NUMBER_M5 = 20260611

# Late-Night Window (02:00 - 06:00 WIB): Max layers encountered: 9.
# Daytime Window (08:00 - 12:00 WIB): Max layers encountered: 9.
# min = 11, max = 44
LOT_SIZE = 0.01 * 11
MAX_SPREAD_USD = 30
SPREAD_DEDUCTION_USD = 0.03
MAX_CONCURRENT_POSITIONS = 1

EMA_FAST, EMA_MED, EMA_SLOW = 5, 21, 200
H1_EMA_PERIOD, RSI_PERIOD, ATR_PERIOD = 50, 7, 14
ADX_PERIOD, VOL_EMA_PERIOD = 14, 10
RSI_PERIOD_M1, RSI_LIMIT_UP_M1, RSI_LIMIT_DOWN_M1 = 7, 80, 20


# Layering Strategy Config
LAYERING_MODE = "USD"  # "USD" or "ATR"
LAYERING_STEP_ATR_MULT = 0.300
LAYERING_STEP_USD = 0.300
TAKE_PROFIT_PER_LAYER_USD = 3 * 11
MAX_LAYERS = None  # None for unlimited
EXIT_LOGIC_AND = True  # True: both RSI & close conditions; False: either condition
number_of_normal_layer = 1000
constant = 10

# Low risk overrides (used outside peak hours on weekdays)
# Times to Avoid: 18:00 WIB (max layers 58), 07:00 WIB (max layers 50), 20:00 WIB (max layers 27), and 00:00 WIB (max layers 22).
# min = 1, max = 1
LOW_RISK_OVERRIDES = {
    "LOT_SIZE": 0.01 * 1,
    "LAYERING_STEP_ATR_MULT": 0.300,
    "TAKE_PROFIT_PER_LAYER_USD": 3 * 1,
}

# Moderate risk overrides
# Late-Day Window (08:00 - 18:00 WIB): Max layers encountered: 13.
# min = 5, max = 21
MODERATE_RISK_OVERRIDES = {
    "LOT_SIZE": 0.01 * 5,
    "LAYERING_STEP_ATR_MULT": 0.300,
    "TAKE_PROFIT_PER_LAYER_USD": 3 * 5,
}
