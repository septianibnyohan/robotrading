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
# ACTIVE_SYMBOLS = ["BTCUSDc", "XAUUSDc", "BTCUSDm", "XAUUSDm"]
ACTIVE_SYMBOLS = ["BTCUSDc"]

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
        if name.startswith('__') or name in ('_get_current_time', 'set_active_symbol', '_get_symbol_module', 'ACTIVE_SYMBOLS', 'is_low_risk_time'):
            return super().__getattribute__(name)
            
        if name == 'ACTIVE_SYMBOL':
            return _active_symbol_var.get()
        
        # Check if the attribute was set/patched directly on this proxy module object first
        if name in self.__dict__:
            return super().__getattribute__(name)
            
        # Load active symbol module
        symbol_module = self._get_symbol_module()
        
        # Check if low risk overrides apply
        symbol = _active_symbol_var.get()
        is_low_risk = self.is_low_risk_time()
        
        if is_low_risk:
            import MetaTrader5 as mt5
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
                            has_active_trades = any(p.magic in magic_numbers for p in raw_positions)
                        else:
                            has_active_trades = True
                            
                        if has_active_trades:
                            is_low_risk = False
            except Exception as e:
                logger.error(f"Error checking open positions in btc_config: {e}")
                
        # Return overridden value if in low-risk mode
        if is_low_risk and hasattr(symbol_module, 'LOW_RISK_OVERRIDES') and name in symbol_module.LOW_RISK_OVERRIDES:
            return symbol_module.LOW_RISK_OVERRIDES[name]
            
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
        if name.startswith('__') or name in ('_get_current_time', 'set_active_symbol', '_get_symbol_module', 'ACTIVE_SYMBOLS', 'is_low_risk_time'):
            super().__setattr__(name, value)
        elif name == 'ACTIVE_SYMBOL':
            _active_symbol_var.set(value)
        else:
            symbol_module = self._get_symbol_module()
            setattr(symbol_module, name, value)

    def __delattr__(self, name):
        if name.startswith('__') or name in ('_get_current_time', 'set_active_symbol', '_get_symbol_module', 'ACTIVE_SYMBOLS', 'is_low_risk_time'):
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

    def is_low_risk_time(self):
        symbol = _active_symbol_var.get()
        now = self._get_current_time()
        is_weekend = now.weekday() >= 5
        
        if "XAUUSD" in symbol:
            # Normal config if 07:00 - 16:00 WIB; low risk otherwise
            if not (7 <= now.hour < 16):
                return True
        elif "BTCUSD" in symbol:
            # Weekend -> always normal config
            # Weekday -> normal config if 04:00 - 06:00 or 09:00 - 13:00 WIB; low risk otherwise
            if not is_weekend:
                in_morning_window = (4 <= now.hour < 6)
                in_midday_window = (9 <= now.hour < 13)
                if not (in_morning_window or in_midday_window):
                    return True
        else:
            # Fallback for other symbols: normal config during weekday peak hours (08:00 - 15:00)
            if not is_weekend:
                if not (8 <= now.hour < 15):
                    return True
        return False

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
