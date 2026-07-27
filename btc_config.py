import sys
import types
from datetime import datetime
import importlib
import logging
import contextvars

logger = logging.getLogger(__name__)

# Context-local active symbol
_active_symbol_var = contextvars.ContextVar('active_symbol', default="BTCUSDc")

# Configured active symbols
ACTIVE_SYMBOLS = ["BTCUSDc", "XAUUSDc", "BTCUSDm", "XAUUSDm", "XAGUSDc"]

def set_active_symbol(symbol):
    _active_symbol_var.set(symbol)
    
    # Pre-import the symbol module to verify it exists and log success/failure
    try:
        importlib.import_module(f"config.symbols.{symbol}")
        # logger.info(f"Active symbol configuration set to: {symbol}")
    except ImportError:
        logger.warning(
            f"Configuration module config.symbols.{symbol} not found! "
            f"Falling back to default BTCUSDc config."
        )

class DynamicConfigModule(types.ModuleType):
    def __getattribute__(self, name):
        # Prevent infinite recursion for internal attributes/methods
        if name.startswith('__') or name in ('_get_current_time', 'set_active_symbol', '_get_symbol_module', 'ACTIVE_SYMBOLS', 'is_low_risk_time', 'get_risk_level', 'is_sunday_override_time'):
            return super().__getattribute__(name)
            
        if name == 'ACTIVE_SYMBOL':
            return _active_symbol_var.get()
        
        # Check if the attribute was set/patched directly on this proxy module object first
        if name in self.__dict__:
            return super().__getattribute__(name)
            
        # Load active symbol module
        symbol_module = self._get_symbol_module()
        
        # Check overrides using open positions to preserve active risk based on precedence (low > moderate > normal)
        symbol = _active_symbol_var.get()
        current_risk = self.get_risk_level()
        active_risk = current_risk
        
        is_sunday_override = self.is_sunday_override_time()
        
        import MetaTrader5 as mt5
        from datetime import datetime
        try:
            if mt5.terminal_info() is not None:
                raw_positions = mt5.positions_get(symbol=symbol)
                if raw_positions:
                    magic_numbers = []
                    if hasattr(symbol_module, 'MAGIC_NUMBER'):
                        magic_numbers.append(symbol_module.MAGIC_NUMBER)
                    if hasattr(symbol_module, 'MAGIC_NUMBER_M5'):
                        magic_numbers.append(symbol_module.MAGIC_NUMBER_M5)
                    
                    if magic_numbers:
                        matching_positions = [p for p in raw_positions if p.magic in magic_numbers]
                    else:
                        matching_positions = raw_positions
                        
                    if matching_positions:
                        oldest_pos = min(matching_positions, key=lambda p: p.time)
                        pos_time_local = datetime.fromtimestamp(oldest_pos.time)
                        active_risk = self.get_risk_level(pos_time_local)
                        if self.is_sunday_override_time(pos_time_local):
                            is_sunday_override = True
        except Exception as e:
            logger.error(f"Error checking open positions in btc_config: {e}")
            
        # Return Sunday lot size override first if applicable
        if "BTCUSD" in symbol and name == "LOT_SIZE" and is_sunday_override:
            return 0.01

        if "BTCUSD" in symbol and name == "TAKE_PROFIT_PER_LAYER_USD" and is_sunday_override:
            return 0.20
            
        # Return overridden value if in low-risk mode
        if active_risk == "low" and hasattr(symbol_module, 'LOW_RISK_OVERRIDES') and name in symbol_module.LOW_RISK_OVERRIDES:
            return symbol_module.LOW_RISK_OVERRIDES[name]
        # Return overridden value if in moderate-risk mode
        elif active_risk == "moderate" and hasattr(symbol_module, 'MODERATE_RISK_OVERRIDES') and name in symbol_module.MODERATE_RISK_OVERRIDES:
            return symbol_module.MODERATE_RISK_OVERRIDES[name]
            
        # Return standard attribute
        if hasattr(symbol_module, name):
            return getattr(symbol_module, name)
            
        # Fallback to module's own attributes (e.g. methods or other globals)
        try:
            return super().__getattribute__(name)
        except AttributeError:
            raise AttributeError(
                f"Module 'btc_config' has no attribute '{name}' "
                f"(Active symbol configuration: {self.ACTIVE_SYMBOL})"
            )

    def __setattr__(self, name, value):
        if name.startswith('__') or name in ('_get_current_time', 'set_active_symbol', '_get_symbol_module', 'ACTIVE_SYMBOLS', 'is_low_risk_time', 'get_risk_level', 'is_sunday_override_time'):
            super().__setattr__(name, value)
        elif name == 'ACTIVE_SYMBOL':
            _active_symbol_var.set(value)
        else:
            symbol_module = self._get_symbol_module()
            setattr(symbol_module, name, value)

    def __delattr__(self, name):
        if name.startswith('__') or name in ('_get_current_time', 'set_active_symbol', '_get_symbol_module', 'ACTIVE_SYMBOLS', 'is_low_risk_time', 'get_risk_level', 'is_sunday_override_time'):
            super().__delattr__(name)
        elif name == 'ACTIVE_SYMBOL':
            _active_symbol_var.set("BTCUSDc")
        else:
            symbol_module = self._get_symbol_module()
            try:
                delattr(symbol_module, name)
            except AttributeError:
                if name in self.__dict__:
                    super().__delattr__(name)

    def is_sunday_override_time(self, dt=None):
        if dt is None:
            now = self._get_current_time()
        else:
            now = dt
        weekday = now.weekday()
        hour = now.hour
        # Sunday 20:00 - 22:00 WIB or Monday 01:00 - 12:00 WIB
        if (weekday == 6 and 20 <= hour < 22) or (weekday == 0 and 1 <= hour < 12):
            return True
        return False

    def get_risk_level(self, dt=None):
        symbol = _active_symbol_var.get()
        if dt is None:
            now = self._get_current_time()
        else:
            now = dt
        is_weekend = now.weekday() >= 5
        
        if "BTCUSD" in symbol:
            # WIB check:
            # normal risk : 22:00 - 01:00 WIB
            # moderate risk: 12:00 - 20:00 WIB
            # other time use low risk
            hour = now.hour
            if hour >= 22 or hour < 1:
                return "normal"
            elif 12 <= hour < 20:
                return "moderate"
            else:
                return "low"
        elif "XAUUSD" in symbol:
            # normal risk : 01:00 - 05:00 WIB
            # moderate risk: 22:00 - 04:00 WIB
            # other time use low risk
            hour = now.hour
            if 1 <= hour < 5:
                return "normal"
            elif hour >= 22 or hour < 4:
                return "moderate"
            else:
                return "low"
        elif "XAGUSD" in symbol:
            # normal risk : 02:00 - 06:00 WIB and 08:00 - 12:00 WIB
            # moderate risk: 12:00 - 18:00 WIB
            # other time use low risk
            hour = now.hour
            if (2 <= hour < 6) or (8 <= hour < 12):
                return "normal"
            elif 12 <= hour < 18:
                return "moderate"
            else:
                return "low"
        else:
            # Fallback for other symbols: normal config during weekday peak hours (08:00 - 15:00)
            if not is_weekend and (8 <= now.hour < 15):
                return "normal"
            return "low"

    def is_low_risk_time(self, dt=None):
        return self.get_risk_level(dt) == "low"

    def _get_current_time(self):
        return datetime.now()
        
    def _get_symbol_module(self):
        symbol = _active_symbol_var.get()
        try:
            return importlib.import_module(f"config.symbols.{symbol}")
        except ImportError:
            # Fallback to loading default symbol config
            return importlib.import_module("config.symbols.BTCUSDc")

# Override this module's class in sys.modules to enable dynamic lookup
sys.modules[__name__].__class__ = DynamicConfigModule
