import sys
import types
from datetime import datetime
import importlib
import logging
import contextvars

logger = logging.getLogger(__name__)

# Context-local active symbol
_active_symbol_var = contextvars.ContextVar('active_symbol', default="BTCUSDc")
_active_risk_var = contextvars.ContextVar('active_risk', default=None)
_active_sunday_override_var = contextvars.ContextVar('active_sunday_override', default=None)

# Configured active symbols
ACTIVE_SYMBOLS = ["BTCUSDc", "XAUUSDc", "BTCUSDm", "XAUUSDm", "XAGUSDc", "ETHUSDc"]

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

def set_active_risk(risk, sunday_override):
    _active_risk_var.set(risk)
    _active_sunday_override_var.set(sunday_override)

def clear_active_risk():
    _active_risk_var.set(None)
    _active_sunday_override_var.set(None)

class DynamicConfigModule(types.ModuleType):
    _gui_settings_cache = None
    _gui_settings_mtime = 0

    def _get_gui_settings(self):
        import json
        import os
        settings_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config", "gui_settings.json")
        if not os.path.exists(settings_path):
            return {}
        try:
            mtime = os.path.getmtime(settings_path)
            if self._gui_settings_cache is None or mtime > self._gui_settings_mtime:
                with open(settings_path, 'r') as f:
                    self._gui_settings_cache = json.load(f)
                self._gui_settings_mtime = mtime
        except Exception as e:
            if self._gui_settings_cache is not None:
                return self._gui_settings_cache
            return {}
        return self._gui_settings_cache

    def set_active_risk(self, risk, sunday_override):
        set_active_risk(risk, sunday_override)

    def clear_active_risk(self):
        clear_active_risk()

    def __getattribute__(self, name):
        # Prevent infinite recursion for internal attributes/methods
        if name.startswith('__') or name in ('_get_current_time', 'set_active_symbol', 'set_active_risk', 'clear_active_risk', '_get_symbol_module', 'ACTIVE_SYMBOLS', 'is_low_risk_time', 'get_risk_level', 'is_sunday_override_time', '_get_gui_settings', '_gui_settings_cache', '_gui_settings_mtime'):
            return super().__getattribute__(name)
            
        if name == 'ACTIVE_SYMBOL':
            return _active_symbol_var.get()
        
        # Check if the attribute was set/patched directly on this proxy module object first
        if name in self.__dict__:
            return super().__getattribute__(name)
            
        # Load active symbol module
        symbol_module = self._get_symbol_module()
        symbol = _active_symbol_var.get()
        gui_settings = self._get_gui_settings()
        
        # Check overrides using open positions to preserve active risk based on precedence (low > moderate > normal)
        context_risk = _active_risk_var.get()
        context_sunday = _active_sunday_override_var.get()
        
        if context_risk is not None:
            active_risk = context_risk
            is_sunday_override = context_sunday if context_sunday is not None else False
        else:
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
                        gui_sym_config = gui_settings.get(symbol, {})
                        magic_num = gui_sym_config.get('MAGIC_NUMBER', getattr(symbol_module, 'MAGIC_NUMBER', None))
                        magic_num_m5 = gui_sym_config.get('MAGIC_NUMBER_M5', getattr(symbol_module, 'MAGIC_NUMBER_M5', None))
                        magic_num_m15 = gui_sym_config.get('MAGIC_NUMBER_M15', getattr(symbol_module, 'MAGIC_NUMBER_M15', None))
                        if magic_num is not None:
                            magic_numbers.append(magic_num)
                        if magic_num_m5 is not None:
                            magic_numbers.append(magic_num_m5)
                        if magic_num_m15 is not None:
                            magic_numbers.append(magic_num_m15)
                        
                        if magic_numbers:
                            matching_positions = [p for p in raw_positions if p.magic in magic_numbers]
                        else:
                            matching_positions = raw_positions
                            
                        if matching_positions:
                            oldest_pos = min(matching_positions, key=lambda p: p.time)
                            from zoneinfo import ZoneInfo
                            from datetime import timezone
                            wib_tz = ZoneInfo("Asia/Jakarta")
                            pos_time_wib = datetime.fromtimestamp(oldest_pos.time, timezone.utc).astimezone(wib_tz).replace(tzinfo=None)
                            active_risk = self.get_risk_level(pos_time_wib)
                            if self.is_sunday_override_time(pos_time_wib):
                                is_sunday_override = True
            except Exception as e:
                logger.error(f"Error checking open positions in btc_config: {e}")
            
        # Return Sunday lot size override first if applicable
        if ("BTCUSD" in symbol or "ETHUSD" in symbol) and name == "LOT_SIZE" and is_sunday_override:
            return 0.01

        if name == "TAKE_PROFIT_PER_LAYER_USD" and is_sunday_override:
            if "BTCUSD" in symbol:
                return 0.20
            elif "ETHUSD" in symbol:
                return 0.02
            
        gui_sym_config = gui_settings.get(symbol, {})
        # Return overridden value if in low-risk mode
        if active_risk == "low":
            low_risk_overrides = gui_sym_config.get('LOW_RISK_OVERRIDES', getattr(symbol_module, 'LOW_RISK_OVERRIDES', {}))
            if name in low_risk_overrides:
                return low_risk_overrides[name]
        # Return overridden value if in moderate-risk mode
        elif active_risk == "moderate":
            mod_risk_overrides = gui_sym_config.get('MODERATE_RISK_OVERRIDES', getattr(symbol_module, 'MODERATE_RISK_OVERRIDES', {}))
            if name in mod_risk_overrides:
                return mod_risk_overrides[name]
            
        # Return GUI override if set
        if name in gui_sym_config:
            return gui_sym_config[name]

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
        if name.startswith('__') or name in ('_get_current_time', 'set_active_symbol', '_get_symbol_module', 'ACTIVE_SYMBOLS', 'is_low_risk_time', 'get_risk_level', 'is_sunday_override_time', '_get_gui_settings', '_gui_settings_cache', '_gui_settings_mtime'):
            super().__setattr__(name, value)
        elif name == 'ACTIVE_SYMBOL':
            _active_symbol_var.set(value)
        else:
            symbol_module = self._get_symbol_module()
            setattr(symbol_module, name, value)

    def __delattr__(self, name):
        if name.startswith('__') or name in ('_get_current_time', 'set_active_symbol', '_get_symbol_module', 'ACTIVE_SYMBOLS', 'is_low_risk_time', 'get_risk_level', 'is_sunday_override_time', '_get_gui_settings', '_gui_settings_cache', '_gui_settings_mtime'):
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
        
        if "BTCUSD" in symbol or "ETHUSD" in symbol:
            hour = now.hour
            if hour >= 22 or hour < 1:
                return "normal"
            elif 12 <= hour < 20:
                return "moderate"
            else:
                return "low"
        elif "XAUUSD" in symbol:
            hour = now.hour
            if 1 <= hour < 5:
                return "normal"
            elif hour >= 22 or hour < 4:
                return "moderate"
            else:
                return "low"
        elif "XAGUSD" in symbol:
            hour = now.hour
            if (2 <= hour < 6) or (8 <= hour < 12):
                return "normal"
            elif 12 <= hour < 18:
                return "moderate"
            else:
                return "low"
        else:
            if not is_weekend and (8 <= now.hour < 15):
                return "normal"
            return "low"

    def is_low_risk_time(self, dt=None):
        return self.get_risk_level(dt) == "low"

    def _get_current_time(self):
        from datetime import datetime, timezone
        from zoneinfo import ZoneInfo
        wib_tz = ZoneInfo("Asia/Jakarta")
        return datetime.now(timezone.utc).astimezone(wib_tz).replace(tzinfo=None)
        
    def _get_symbol_module(self):
        symbol = _active_symbol_var.get()
        try:
            return importlib.import_module(f"config.symbols.{symbol}")
        except ImportError:
            return importlib.import_module("config.symbols.BTCUSDc")

# Override this module's class in sys.modules to enable dynamic lookup
sys.modules[__name__].__class__ = DynamicConfigModule
