import sys
import time
import logging
from datetime import datetime, timezone
import MetaTrader5 as mt5

from btc_config import (
    SYMBOL, MAX_SPREAD_USD, EMA_SLOW, LAYERING_MODE, LAYERING_STEP_ATR_MULT,
    LAYERING_STEP_USD, TAKE_PROFIT_PER_LAYER_USD, MAX_LAYERS, EXIT_LOGIC_AND
)
from btc_indicators import (
    calculate_m1_layer_indicators, calculate_h1_layer_indicators, rates_to_df
)
from btc_risk import get_daily_realized_profit, check_circuit_breaker
from btc_trading import (
    initialize_mt5, open_trade, close_all_open_positions
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler("btc_layer_bot.log"), logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

def recover_layer_state(positions):
    """Recovers the state of the active layer from open positions."""
    if not positions:
        return None
    oldest = min(positions, key=lambda p: p.time)
    direction = "BUY" if oldest.type == mt5.POSITION_TYPE_BUY else "SELL"
    return {
        "direction": direction,
        "first_entry_price": oldest.price_open,
        "total_layers": len(positions)
    }

def check_h1_signal(h1_row):
    """Evaluates the H1 signal (Buy: Close > EMA200; Sell: Close < EMA200)."""
    close, ema_200 = h1_row['close'], h1_row['ema_200']
    buy_ok = bool(close > ema_200)
    sell_ok = bool(close < ema_200)
    logger.info(f"[H1 Trend] Close: {close:.2f}, EMA200: {ema_200:.2f} (Buy: {buy_ok}, Sell: {sell_ok})")
    if buy_ok:
        return "BUY"
    if sell_ok:
        return "SELL"
    return None

def check_m1_crossover(m1_df):
    """Evaluates M1 RSI crossover (Buy: cross up 30; Sell: cross down 70)."""
    if len(m1_df) < 3:
        return None
    m1_c, m1_p = m1_df.iloc[-2], m1_df.iloc[-3]
    rsi_curr, rsi_prev = m1_c['rsi_14'], m1_p['rsi_14']
    buy_cross = bool(rsi_prev <= 30 < rsi_curr)
    sell_cross = bool(rsi_prev >= 70 > rsi_curr)
    logger.info(f"[M1 RSI] RSI Curr: {rsi_curr:.2f}, Prev: {rsi_prev:.2f} (CrossUp30: {buy_cross}, CrossDown70: {sell_cross})")
    if buy_cross:
        return "BUY"
    if sell_cross:
        return "SELL"
    return None

def check_h1_exit_conditions(h1_row, direction):
    """Checks if the H1 trend invalidation exit conditions are met."""
    close, ema_200, rsi = h1_row['close'], h1_row['ema_200'], h1_row['rsi_14']
    logger.info(f"[H1 EXIT EVAL] Direction: {direction}, Close: {close:.2f}, EMA200: {ema_200:.2f}, RSI: {rsi:.2f}")
    cond_rsi = rsi <= 40 if direction == "BUY" else rsi >= 50
    cond_close = close <= ema_200 if direction == "BUY" else close >= ema_200
    if EXIT_LOGIC_AND:
        return cond_rsi and cond_close
    return cond_rsi or cond_close

def get_layer_step(h1_row):
    """Calculates grid spacing step in USD."""
    if LAYERING_MODE == "ATR":
        atr = h1_row['atr_14'] if 'atr_14' in h1_row else 100.0
        return atr * LAYERING_STEP_ATR_MULT
    return LAYERING_STEP_USD

def handle_layering(positions, state, step, tick):
    """Applies grid layering when the price moves against the first entry."""
    direction, first_entry_price = state["direction"], state["first_entry_price"]
    total_layers = state["total_layers"]
    if MAX_LAYERS is not None and total_layers >= MAX_LAYERS:
        return
    offset = total_layers * step
    if direction == "BUY" and tick.ask <= first_entry_price - offset:
        logger.info(f"[LAYERING] Triggering Buy Layer {total_layers + 1}. Price: {tick.ask:.2f}")
        ticket = open_trade("BUY", tick.ask, 0.0, 0.0)
        if ticket:
            state["total_layers"] += 1
    elif direction == "SELL" and tick.bid >= first_entry_price + offset:
        logger.info(f"[LAYERING] Triggering Sell Layer {total_layers + 1}. Price: {tick.bid:.2f}")
        ticket = open_trade("SELL", tick.bid, 0.0, 0.0)
        if ticket:
            state["total_layers"] += 1

def handle_basket_tp(positions, state):
    """Checks basket profit and closes all positions if Take Profit target is met."""
    total_profit = sum(p.profit + p.swap for p in positions)
    total_layers = state["total_layers"]
    target_profit = TAKE_PROFIT_PER_LAYER_USD * total_layers
    logger.debug(f"[BASKET TP CHECK] Profit: {total_profit:.2f} USD, Target: {target_profit:.2f} USD")
    if total_profit >= target_profit:
        logger.info(f"[BASKET TP] Take Profit met ({total_profit:.2f} >= {target_profit:.2f}). Closing all...")
        close_all_open_positions("BASKET_TP")
        return True
    return False

def check_and_trigger_entry(h1_row, m1_df, tick):
    """Checks entry conditions and opens the first position of the layer."""
    h1_signal = check_h1_signal(h1_row)
    m1_cross = check_m1_crossover(m1_df)
    if h1_signal is not None and h1_signal == m1_cross:
        price = tick.ask if h1_signal == "BUY" else tick.bid
        logger.info(f"[ENTRY] Trend ({h1_signal}) and M1 RSI crossover aligned. Opening Layer 1 at {price:.2f}")
        ticket = open_trade(h1_signal, price, 0.0, 0.0)
        if ticket:
            return {
                "direction": h1_signal,
                "first_entry_price": price,
                "total_layers": 1
            }
    return None

def handle_h1_exit_eval(h1_row, positions, state):
    """Evaluates H1 exit conditions and closes all positions if triggered."""
    # direction = state["direction"]
    # if check_h1_exit_conditions(h1_row, direction):
    #     logger.info(f"[H1 EXIT] Invalidation exit triggered for {direction}. Closing all positions...")
    #     close_all_open_positions("H1_INVALIDATION")
    #     return True
    return False

def fetch_indicators_data():
    """Fetches and calculates H1 and M1 indicators."""
    h1_rates = mt5.copy_rates_from_pos(SYMBOL, mt5.TIMEFRAME_H1, 0, 300)
    m1_rates = mt5.copy_rates_from_pos(SYMBOL, mt5.TIMEFRAME_M1, 0, 100)
    if h1_rates is None or m1_rates is None:
        return None, None
    h1_df = calculate_h1_layer_indicators(rates_to_df(h1_rates))
    m1_df = calculate_m1_layer_indicators(rates_to_df(m1_rates))
    return h1_df, m1_df

def is_spread_valid(tick):
    """Checks if current spread is within allowed limits."""
    spread = tick.ask - tick.bid
    if spread > MAX_SPREAD_USD:
        logger.warning(f"Spread {spread:.2f} exceeds limit {MAX_SPREAD_USD:.2f}.")
        return False
    return True

def process_loop_logic(positions, state, h1_df, m1_df, h1_row, tick, loop_state, starting_balance):
    """Processes entry, layering, take profit, and exit checks for a loop iteration."""
    if positions:
        if handle_basket_tp(positions, state):
            return None
        step = get_layer_step(h1_row)
        handle_layering(positions, state, step, tick)
        completed_m1_time = m1_df.iloc[-2]['time']
        if loop_state["last_m1_time"] is None or completed_m1_time > loop_state["last_m1_time"]:
            loop_state["last_m1_time"] = completed_m1_time
            total_profit = sum(p.profit + p.swap for p in positions)
            offset = state["total_layers"] * step
            trigger = state["first_entry_price"] - offset if state["direction"] == "BUY" else state["first_entry_price"] + offset
            logger.info(f"[Basket Log] Layers: {state['total_layers']} | Net Profit: {total_profit:.2f} USD (Target TP: {TAKE_PROFIT_PER_LAYER_USD * state['total_layers']:.2f} USD) | Next Trigger: {trigger:.2f}")
        completed_h1_time = h1_df.iloc[-2]['time']
        if loop_state["last_h1_time"] is None or completed_h1_time > loop_state["last_h1_time"]:
            loop_state["last_h1_time"] = completed_h1_time
            if handle_h1_exit_eval(h1_row, positions, state):
                return None
    else:
        is_ok, _ = check_circuit_breaker(starting_balance)
        if not is_ok:
            return None
        completed_m1_time = m1_df.iloc[-2]['time']
        if loop_state["last_m1_time"] is None or completed_m1_time > loop_state["last_m1_time"]:
            loop_state["last_m1_time"] = completed_m1_time
            state = check_and_trigger_entry(h1_row, m1_df, tick)
    return state

def run_trading_loop(starting_balance):
    """Orchestrates layering strategy checking tick data and completed candles."""
    logger.info("Entering trading loop...")
    loop_state = {"last_h1_time": None, "last_m1_time": None}
    state = None
    try:
        while True:
            tick = mt5.symbol_info_tick(SYMBOL)
            positions = mt5.positions_get(symbol=SYMBOL)
            if not positions:
                state = None
            elif state is None:
                state = recover_layer_state(positions)
            if tick and is_spread_valid(tick):
                h1_df, m1_df = fetch_indicators_data()
                if h1_df is not None and m1_df is not None:
                    h1_row = h1_df.iloc[-2]
                    state = process_loop_logic(positions, state, h1_df, m1_df, h1_row, tick, loop_state, starting_balance)
            time.sleep(1.0)
    except KeyboardInterrupt:
        logger.info("Shutdown requested. Closing all positions...")
        close_all_open_positions("Shutdown")
    finally:
        mt5.shutdown()

def main():
    initialize_mt5()
    account_info = mt5.account_info()
    if not account_info:
        sys.exit(1)
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    starting_balance = account_info.balance - get_daily_realized_profit(today)
    run_trading_loop(starting_balance)

if __name__ == "__main__":
    main()
