import sys
import logging
import MetaTrader5 as mt5
import btc_config

logger = logging.getLogger(__name__)

def initialize_mt5():
    """Initializes connection to MT5 terminal."""
    if not mt5.initialize():
        logger.error(f"MT5 init failed: {mt5.last_error()}")
        sys.exit(1)
    if not mt5.symbol_select(btc_config.SYMBOL, True):
        logger.error(f"Symbol {btc_config.SYMBOL} select failed.")
        mt5.shutdown()
        sys.exit(1)
    logger.info("MT5 connection and symbol check completed successfully.")

def get_filling_type(symbol):
    """Retrieves appropriate order filling mode dynamically."""
    info = mt5.symbol_info(symbol)
    if info is None:
        return mt5.ORDER_FILLING_IOC
    filling = info.filling_mode
    if filling & 2:  # SYMBOL_FILLING_IOC is bit 2 (IOC)
        return mt5.ORDER_FILLING_IOC
    if filling & 1:  # SYMBOL_FILLING_FOK is bit 1 (FOK)
        return mt5.ORDER_FILLING_FOK
    return mt5.ORDER_FILLING_RETURN

def close_position_by_ticket(ticket, volume, pos_type, exit_reason, symbol=None):
    """Sends close request to MT5."""
    target_symbol = symbol
    if target_symbol is None:
        positions = mt5.positions_get(ticket=ticket)
        if positions:
            target_symbol = positions[0].symbol
        else:
            target_symbol = btc_config.SYMBOL

    tick = mt5.symbol_info_tick(target_symbol)
    if tick is None:
        logger.error(f"Failed to get tick for symbol: {target_symbol}")
        return False
    positions = mt5.positions_get(ticket=ticket)
    est_profit = positions[0].profit if positions else 0.0
    order_type = mt5.ORDER_TYPE_SELL if pos_type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_BUY
    price = tick.bid if pos_type == mt5.POSITION_TYPE_BUY else tick.ask
    
    # Retrieve magic number and spread deduction dynamically
    magic_number = btc_config.MAGIC_NUMBER
    spread_deduction = btc_config.SPREAD_DEDUCTION_USD
    if target_symbol != btc_config.SYMBOL:
        try:
            import importlib
            sym_mod = importlib.import_module(f"config.symbols.{target_symbol}")
            magic_number = getattr(sym_mod, "MAGIC_NUMBER", magic_number)
            spread_deduction = getattr(sym_mod, "SPREAD_DEDUCTION_USD", spread_deduction)
        except Exception:
            pass

    request = {
        "action": mt5.TRADE_ACTION_DEAL, "symbol": target_symbol, "volume": float(volume),
        "type": order_type, "position": ticket, "price": price,
        "deviation": 20, "magic": magic_number, "comment": f"Close {exit_reason}",
        "type_time": mt5.ORDER_TIME_GTC, "type_filling": get_filling_type(target_symbol),
    }
    res = mt5.order_send(request)
    if res is None:
        logger.error(f"Failed to close {ticket} for {target_symbol}: order_send returned None. MT5 Error: {mt5.last_error()}")
        return False
    if res.retcode != mt5.TRADE_RETCODE_DONE:
        logger.error(f"Failed to close {ticket} for {target_symbol}: {res.comment}")
        return False
    logger.info(f"Closed {ticket} ({exit_reason}). Net Profit: {est_profit - spread_deduction:.2f} USD")
    
    try:
        from data.trade_logger import TradeRsiLogger
        db_logger = TradeRsiLogger()
        spread_val = tick.ask - tick.bid if tick is not None else None
        db_logger.log_trade(ticket, "CLOSED", target_symbol, price, volume, profit=est_profit, spread=spread_val)
    except Exception as ex:
        logger.error(f"Error logging close to DB: {ex}")
        
    return True

def close_all_open_positions(reason="Shutdown", symbol=None, magic=None):
    """Closes active positions for the specified symbol matching the magic number."""
    target_symbol = symbol if symbol is not None else btc_config.SYMBOL
    target_magic = magic
    if target_magic is None:
        target_magic = btc_config.MAGIC_NUMBER
        if target_symbol != btc_config.SYMBOL:
            try:
                import importlib
                sym_mod = importlib.import_module(f"config.symbols.{target_symbol}")
                target_magic = getattr(sym_mod, "MAGIC_NUMBER", target_magic)
            except Exception:
                pass

    raw_positions = mt5.positions_get(symbol=target_symbol)
    if raw_positions:
        positions = [p for p in raw_positions if p.magic == target_magic]
        for pos in positions:
            close_position_by_ticket(pos.ticket, pos.volume, pos.type, reason, symbol=target_symbol)

def close_all_open_position(reason="Shutdown", symbol=None):
    """Closes all active positions for the specified symbol (alias)."""
    close_all_open_positions(reason=reason, symbol=symbol)

def modify_position_sl(ticket, sl_price, tp_price, symbol=None):
    """Modifies the Stop Loss and Take Profit levels."""
    target_symbol = symbol if symbol is not None else btc_config.SYMBOL
    request = {
        "action": mt5.TRADE_ACTION_SLTP, "position": int(ticket),
        "symbol": target_symbol, "sl": float(sl_price), "tp": float(tp_price),
    }
    result = mt5.order_send(request)
    if result is None:
        logger.error(f"Failed to modify SL/TP for {ticket}: order_send returned None. MT5 Error: {mt5.last_error()}")
        return False
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        return False
    logger.info(f"Modified {ticket}: SL={sl_price:.2f}, TP={tp_price:.2f}")
    return True

def open_trade(direction, entry_price, sl_price, tp_price, symbol=None, magic=None):
    """Sends order to open new position."""
    target_symbol = symbol if symbol is not None else btc_config.SYMBOL
    
    # Retrieve configuration values dynamically
    lot_size = btc_config.LOT_SIZE
    magic_number = magic
    if magic_number is None:
        magic_number = btc_config.MAGIC_NUMBER
        if target_symbol != btc_config.SYMBOL:
            try:
                import importlib
                sym_mod = importlib.import_module(f"config.symbols.{target_symbol}")
                magic_number = getattr(sym_mod, "MAGIC_NUMBER", magic_number)
            except Exception:
                pass

    order_type = mt5.ORDER_TYPE_BUY if direction == "BUY" else mt5.ORDER_TYPE_SELL
    request = {
        "action": mt5.TRADE_ACTION_DEAL, "symbol": target_symbol, "volume": float(lot_size),
        "type": order_type, "price": float(entry_price), "sl": float(sl_price), "tp": float(tp_price),
        "deviation": 20, "magic": magic_number, "comment": f"{target_symbol} entry",
        "type_time": mt5.ORDER_TIME_GTC, "type_filling": get_filling_type(target_symbol),
    }
    res = mt5.order_send(request)
    if res is None:
        logger.error(f"Failed {direction} entry for {target_symbol}: order_send returned None. MT5 Error: {mt5.last_error()}")
        return None
    if res.retcode != mt5.TRADE_RETCODE_DONE:
        logger.error(f"Failed {direction} entry: {res.comment}")
        return None
    logger.info(f"Opened {direction} ({res.order}) at {entry_price:.2f}")
    
    try:
        from data.trade_logger import TradeRsiLogger
        db_logger = TradeRsiLogger()
        spread_val = None
        try:
            tick = mt5.symbol_info_tick(target_symbol)
            if tick is not None:
                spread_val = tick.ask - tick.bid
        except Exception:
            pass
        db_logger.log_trade(res.order, direction, target_symbol, entry_price, lot_size, spread=spread_val)
    except Exception as ex:
        logger.error(f"Error logging trade to DB: {ex}")
        
    return res.order

