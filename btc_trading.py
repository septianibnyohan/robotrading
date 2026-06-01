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
        return mt5.ORDER_FILLING_FOK
    filling = info.filling_mode
    if filling & 1:  # SYMBOL_FILLING_FOK is bit 1 (FOK)
        return mt5.ORDER_FILLING_FOK
    if filling & 2:  # SYMBOL_FILLING_IOC is bit 2 (IOC)
        return mt5.ORDER_FILLING_IOC
    return mt5.ORDER_FILLING_RETURN

def close_position_by_ticket(ticket, volume, pos_type, exit_reason):
    """Sends close request to MT5."""
    tick = mt5.symbol_info_tick(btc_config.SYMBOL)
    if tick is None:
        return False
    positions = mt5.positions_get(ticket=ticket)
    est_profit = positions[0].profit if positions else 0.0
    order_type = mt5.ORDER_TYPE_SELL if pos_type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_BUY
    price = tick.bid if pos_type == mt5.POSITION_TYPE_BUY else tick.ask
    request = {
        "action": mt5.TRADE_ACTION_DEAL, "symbol": btc_config.SYMBOL, "volume": float(volume),
        "type": order_type, "position": ticket, "price": price,
        "deviation": 20, "magic": btc_config.MAGIC_NUMBER, "comment": f"Close {exit_reason}",
        "type_time": mt5.ORDER_TIME_GTC, "type_filling": get_filling_type(btc_config.SYMBOL),
    }
    res = mt5.order_send(request)
    if res.retcode != mt5.TRADE_RETCODE_DONE:
        logger.error(f"Failed to close {ticket}: {res.comment}")
        return False
    logger.info(f"Closed {ticket} ({exit_reason}). Net Profit: {est_profit - btc_config.SPREAD_DEDUCTION_USD:.2f} USD")
    return True

def close_all_open_positions(reason="Shutdown"):
    """Closes all active positions."""
    positions = mt5.positions_get(symbol=btc_config.SYMBOL)
    if positions:
        for pos in positions:
            close_position_by_ticket(pos.ticket, pos.volume, pos.type, reason)

def modify_position_sl(ticket, sl_price, tp_price):
    """Modifies the Stop Loss and Take Profit levels."""
    request = {
        "action": mt5.TRADE_ACTION_SLTP, "position": int(ticket),
        "symbol": SYMBOL, "sl": float(sl_price), "tp": float(tp_price),
    }
    result = mt5.order_send(request)
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        return False
    logger.info(f"Modified {ticket}: SL={sl_price:.2f}, TP={tp_price:.2f}")
    return True

def open_trade(direction, entry_price, sl_price, tp_price):
    """Sends order to open new position."""
    order_type = mt5.ORDER_TYPE_BUY if direction == "BUY" else mt5.ORDER_TYPE_SELL
    request = {
        "action": mt5.TRADE_ACTION_DEAL, "symbol": btc_config.SYMBOL, "volume": float(btc_config.LOT_SIZE),
        "type": order_type, "price": float(entry_price), "sl": float(sl_price), "tp": float(tp_price),
        "deviation": 20, "magic": btc_config.MAGIC_NUMBER, "comment": "BTC M5 entry",
        "type_time": mt5.ORDER_TIME_GTC, "type_filling": get_filling_type(btc_config.SYMBOL),
    }
    res = mt5.order_send(request)
    if res.retcode != mt5.TRADE_RETCODE_DONE:
        logger.error(f"Failed {direction} entry: {res.comment}")
        return None
    logger.info(f"Opened {direction} ({res.order}) at {entry_price:.2f}")
    return res.order
