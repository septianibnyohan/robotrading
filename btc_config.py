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
        if name.startswith('__') or name in ('_get_current_time', 'set_active_symbol', '_get_symbol_module', 'ACTIVE_SYMBOLS'):
            return super().__getattribute__(name)
            
        if name == 'ACTIVE_SYMBOL':
            return _active_symbol_var.get()
        
        # Check if the attribute was set/patched directly on this proxy module object first
        if name in self.__dict__:
            return super().__getattribute__(name)
            
        # Load active symbol module
        symbol_module = self._get_symbol_module()
        
        # Check if low risk overrides apply (weekdays outside 08:00 - 15:00)
        now = self._get_current_time()
        is_weekend = now.weekday() >= 5
        is_low_risk = False
        if not is_weekend:
            if not (8 <= now.hour < 15):
                is_low_risk = True
                
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
        if name.startswith('__') or name in ('_get_current_time', 'set_active_symbol', '_get_symbol_module', 'ACTIVE_SYMBOLS'):
            super().__setattr__(name, value)
        elif name == 'ACTIVE_SYMBOL':
            _active_symbol_var.set(value)
        else:
            symbol_module = self._get_symbol_module()
            setattr(symbol_module, name, value)

    def __delattr__(self, name):
        if name.startswith('__') or name in ('_get_current_time', 'set_active_symbol', '_get_symbol_module', 'ACTIVE_SYMBOLS'):
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
