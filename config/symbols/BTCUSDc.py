SYMBOL = "BTCUSDc"
MAGIC_NUMBER = 20260523
MAGIC_NUMBER_M5 = 20260524
MAGIC_NUMBER_M15 = 20260533


# Late-Night Window (22:00 - 01:00 WIB): Max layers encountered: 16.
# min 56, max = 220
LOT_SIZE = 0.01 * (100)
MAX_SPREAD_USD = 15
SPREAD_DEDUCTION_USD = 0.15
MAX_CONCURRENT_POSITIONS = 1

EMA_FAST, EMA_MED, EMA_SLOW = 9, 21, 200
H1_EMA_PERIOD, RSI_PERIOD, ATR_PERIOD = 50, 14, 14
ADX_PERIOD, VOL_EMA_PERIOD = 14, 10
RSI_PERIOD_M1, RSI_LIMIT_UP_M1, RSI_LIMIT_DOWN_M1 = 7, 80, 20


# Layering Strategy Config
LAYERING_MODE = "USD"  # "USD" or "ATR"
LAYERING_STEP_ATR_MULT = 1.0 * (100) # Late-Night Window (23:00 - 03:00 WIB): Max layers reached was 14.
LAYERING_STEP_USD = 100.0
TAKE_PROFIT_PER_LAYER_USD = 0.20 * (100)
MAX_LAYERS = None  # None for unlimited
EXIT_LOGIC_AND = True  # True: both RSI & close conditions; False: either condition
number_of_normal_layer = 200
constant = 2

# Low risk overrides (used outside peak hours on weekdays)
# Times to Avoid: 01:00 WIB (max layers 234), 21:00 WIB (max layers 168), 04:00 WIB (max layers 98), 11:00 WIB (max layers 84), and 06:00 WIB (max layers 70).
# min 0/1 (0.01 lot/56.616), max 2
# 2 - 7
LOW_RISK_OVERRIDES = {
    "LOT_SIZE": 0.01 * (6), # sunday (1), 3, other max(12)
    "LAYERING_STEP_ATR_MULT": 1.0 * 1,
    "TAKE_PROFIT_PER_LAYER_USD": 0.20 * (6), #1
}

# Moderate risk overrides
# Daytime Window (11:00 - 17:00 WIB): Max layers encountered: 26.
# min 21, max 50
MODERATE_RISK_OVERRIDES = {
    "LOT_SIZE": 0.01 * (43), # Asian Session Window (07:00 - 15:00 WIB): Max layers reached was 24
    "LAYERING_STEP_ATR_MULT": 1.0 * 1,
    "TAKE_PROFIT_PER_LAYER_USD": 0.20 * (43), #25 - 100
}
