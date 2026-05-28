import logging
import MetaTrader5 as mt5
from btc_config import SYMBOL
from btc_trading import modify_position_sl, close_position_by_ticket

logger = logging.getLogger(__name__)

def handle_trailing_stop(pos, tick, state):
    """Trails SL after +1.5% profit."""
    bid, ask = tick.bid, tick.ask
    entry, atr = state["entry_price"], state["atr_at_entry"]
    if pos.type == mt5.POSITION_TYPE_BUY:
        pct_move = (bid - entry) / entry
        if pct_move >= 0.015 and not state["trailing_active"]:
            logger.info(f"Long profit reached {pct_move*100:.2f}%. Activating trailing stop.")
            state["trailing_active"] = True
        if state["trailing_active"]:
            new_sl = round(bid - atr, 2)
            if new_sl > pos.sl:
                logger.info(f"Trailing SL Buy: Moving SL to {new_sl:.2f}.")
                modify_position_sl(pos.ticket, new_sl, pos.tp)
    elif pos.type == mt5.POSITION_TYPE_SELL:
        pct_move = (entry - ask) / entry
        if pct_move >= 0.015 and not state["trailing_active"]:
            logger.info(f"Short profit reached {pct_move*100:.2f}%. Activating trailing stop.")
            state["trailing_active"] = True
        if state["trailing_active"]:
            new_sl = round(ask + atr, 2)
            if pos.sl == 0.0 or new_sl < pos.sl:
                logger.info(f"Trailing SL Sell: Moving SL to {new_sl:.2f}.")
                modify_position_sl(pos.ticket, new_sl, pos.tp)

def check_time_exit(pos, tick, state):
    """Exits trade if no new extreme within 20 mins."""
    bid, ask = tick.bid, tick.ask
    extreme = bid if pos.type == mt5.POSITION_TYPE_BUY else ask
    if (pos.type == mt5.POSITION_TYPE_BUY and extreme > state["peak_price"]) or \
       (pos.type == mt5.POSITION_TYPE_SELL and extreme < state["peak_price"]):
        logger.info(f"New price extreme reached: {extreme:.2f}")
        state["peak_price"] = extreme
        state["last_peak_time"] = tick.time
    if (tick.time - state["last_peak_time"]) >= 1200:
        logger.info("Time exit conditions met.")
        close_position_by_ticket(pos.ticket, pos.volume, pos.type, "TIME_EXIT")
        return True
    return False
