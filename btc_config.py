import sys
import types
from datetime import datetime
import importlib

SYMBOL = "BTCUSDc"
MAGIC_NUMBER = 20260523
LOT_SIZE = 0.01 * 2
MAX_SPREAD_USD = 15
SPREAD_DEDUCTION_USD = 0.15
MAX_CONCURRENT_POSITIONS = 1

EMA_FAST, EMA_MED, EMA_SLOW = 9, 21, 200
H1_EMA_PERIOD, RSI_PERIOD, ATR_PERIOD = 50, 14, 14
ADX_PERIOD, VOL_EMA_PERIOD = 14, 10

# Layering Strategy Config
LAYERING_MODE = "USD"  # "USD" or "ATR"
LAYERING_STEP_ATR_MULT = 1.0 * 2
LAYERING_STEP_USD = 100.0
TAKE_PROFIT_PER_LAYER_USD = 0.20 * 2
MAX_LAYERS = None  # None for unlimited
EXIT_LOGIC_AND = True  # True: both RSI & close conditions; False: either condition


class DynamicConfigModule(types.ModuleType):
    def __getattribute__(self, name):
        # Exclude internal/dunder names, and the dispatcher internals
        if name.startswith('__') or name in ('_get_active_module', '_low_risk_module', '_get_current_hour'):
            return super().__getattribute__(name)
        
        target_module = self._get_active_module()
        if target_module is self:
            return super().__getattribute__(name)
        else:
            return getattr(target_module, name)

    def __setattr__(self, name, value):
        if name.startswith('__') or name in ('_low_risk_module', '_get_current_hour'):
            super().__setattr__(name, value)
        else:
            target_module = self._get_active_module()
            if target_module is self:
                super().__setattr__(name, value)
            else:
                setattr(target_module, name, value)

    def __delattr__(self, name):
        if name.startswith('__') or name in ('_low_risk_module', '_get_current_hour'):
            super().__delattr__(name)
        else:
            target_module = self._get_active_module()
            if target_module is self:
                super().__delattr__(name)
            else:
                delattr(target_module, name)

    def _get_current_hour(self):
        return datetime.now().hour

    def _get_active_module(self):
        # Current local system time
        hour = self._get_current_hour()
        # if current time >= 08:00 and current time < 15:00, use btc_config (self)
        if 8 <= hour < 15:
            return self
        else:
            if not hasattr(self, '_low_risk_module'):
                self._low_risk_module = importlib.import_module('btc_low_risk_config')
            return self._low_risk_module


# Override this module's class in sys.modules to enable dynamic lookup
sys.modules[__name__].__class__ = DynamicConfigModule
