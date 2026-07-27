import sys
import time
import logging
import threading
from datetime import datetime, timezone
import MetaTrader5 as mt5

import btc_config
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
    logger.info(f"[{btc_config.SYMBOL}][H1 Trend] Close: {close:.2f}, EMA200: {ema_200:.2f} (Buy: {buy_ok}, Sell: {sell_ok})")
    if buy_ok:
        return "BUY"
    if sell_ok:
        return "SELL"
    return None

def check_timeframe_crossover(df, tf_name):
    """Evaluates RSI crossover for the specified timeframe (Buy: cross up 20; Sell: cross down 80)."""
    if len(df) < 3:
        return None
    c, p = df.iloc[-2], df.iloc[-3]
    rsi_curr, rsi_prev = c['rsi_14'], p['rsi_14']
    limit_down = getattr(btc_config, 'RSI_LIMIT_DOWN_M1', 20)
    limit_up = getattr(btc_config, 'RSI_LIMIT_UP_M1', 80)
    buy_cross = bool(rsi_prev <= limit_down < rsi_curr)
    sell_cross = bool(rsi_prev >= limit_up > rsi_curr)
    logger.info(f"[{btc_config.SYMBOL}][{tf_name} RSI] RSI Curr: {rsi_curr:.2f}, Prev: {rsi_prev:.2f} (CrossUp{limit_down}: {buy_cross}, CrossDown{limit_up}: {sell_cross})")
    if buy_cross:
        return "BUY"
    if sell_cross:
        return "SELL"
    return None

def check_m1_crossover(m1_df):
    """Evaluates M1 RSI crossover (Buy: cross up 20; Sell: cross down 80)."""
    return check_timeframe_crossover(m1_df, "M1")

def check_h1_exit_conditions(h1_row, direction):
    """Checks if the H1 trend invalidation exit conditions are met."""
    close, ema_200, rsi = h1_row['close'], h1_row['ema_200'], h1_row['rsi_14']
    logger.info(f"[H1 EXIT EVAL] Direction: {direction}, Close: {close:.2f}, EMA200: {ema_200:.2f}, RSI: {rsi:.2f}")
    cond_rsi = rsi <= 40 if direction == "BUY" else rsi >= 50
    cond_close = close <= ema_200 if direction == "BUY" else close >= ema_200
    if btc_config.EXIT_LOGIC_AND:
        return cond_rsi and cond_close
    return cond_rsi or cond_close

def get_layer_step(h1_row):
    """Calculates grid spacing step in USD."""
    if btc_config.LAYERING_MODE == "ATR":
        atr = h1_row['atr_14'] if 'atr_14' in h1_row else 100.0
        return atr * btc_config.LAYERING_STEP_ATR_MULT
    return btc_config.LAYERING_STEP_USD

def handle_layering(positions, state, step, tick):
    """Applies grid layering when the price moves against the first entry."""
    direction, first_entry_price = state["direction"], state["first_entry_price"]
    total_layers = state["total_layers"]
    if btc_config.MAX_LAYERS is not None and total_layers >= btc_config.MAX_LAYERS:
        return
    offset = total_layers * step
    magic_number = btc_config.MAGIC_NUMBER
    if positions:
        pos_magic = getattr(positions[0], "magic", None)
        if isinstance(pos_magic, (int, float)) and not 'Mock' in type(pos_magic).__name__:
            magic_number = int(pos_magic)
    if direction == "BUY" and tick.ask <= first_entry_price - offset:
        logger.info(f"[LAYERING] Triggering Buy Layer {total_layers + 1}. Price: {tick.ask:.2f}")
        ticket = open_trade("BUY", tick.ask, 0.0, 0.0, magic=magic_number)
        if ticket:
            state["total_layers"] += 1
    elif direction == "SELL" and tick.bid >= first_entry_price + offset:
        logger.info(f"[LAYERING] Triggering Sell Layer {total_layers + 1}. Price: {tick.bid:.2f}")
        ticket = open_trade("SELL", tick.bid, 0.0, 0.0, magic=magic_number)
        if ticket:
            state["total_layers"] += 1

def handle_basket_tp(positions, state):
    """Checks basket profit and closes all positions if Take Profit target is met."""
    current_symbol = btc_config.SYMBOL
    symbol_positions = [p for p in positions if p.symbol == current_symbol]
    total_profit = sum(p.profit + p.swap for p in symbol_positions)
    total_layers = state["total_layers"]
    
    # Check risk level based on the oldest position (the one that activated the trade)
    if symbol_positions:
        from datetime import datetime
        oldest_pos = min(symbol_positions, key=lambda p: p.time)
        pos_time_local = datetime.fromtimestamp(oldest_pos.time)
        basket_risk = btc_config.get_risk_level(pos_time_local)
    else:
        basket_risk = "normal"
        
    # Fetch base configuration values directly to prevent clock-time shifts
    import importlib
    try:
        symbol_module = importlib.import_module(f"config.symbols.{current_symbol}")
    except ImportError:
        symbol_module = importlib.import_module("config.symbols.BTCUSDc")
        
    normal_tp = symbol_module.TAKE_PROFIT_PER_LAYER_USD
    low_risk_overrides = getattr(symbol_module, 'LOW_RISK_OVERRIDES', {})
    moderate_risk_overrides = getattr(symbol_module, 'MODERATE_RISK_OVERRIDES', {})
    
    if basket_risk == "normal":
        tp_val = normal_tp
    elif basket_risk == "moderate":
        tp_val = moderate_risk_overrides.get('TAKE_PROFIT_PER_LAYER_USD', normal_tp)
    else:
        tp_val = low_risk_overrides.get('TAKE_PROFIT_PER_LAYER_USD', normal_tp)
        
    target_profit = tp_val * len(symbol_positions)
    
    logger.info(
        f"[{current_symbol} BASKET TP CHECK] Basket risk level: {basket_risk}. "
        f"Target profit based on {len(symbol_positions)} positions: {target_profit:.2f} USD (total profit: {total_profit:.2f} USD)."
    )
        
    logger.debug(f"[{current_symbol} BASKET TP CHECK] Profit: {total_profit:.2f} USD, Target: {target_profit:.2f} USD")
    if total_profit >= target_profit:
        logger.info(f"[{current_symbol} BASKET TP] Take Profit met ({total_profit:.2f} >= {target_profit:.2f}). Closing all positions for {current_symbol}...")
        magic_number = btc_config.MAGIC_NUMBER
        if positions:
            pos_magic = getattr(positions[0], "magic", None)
            if isinstance(pos_magic, (int, float)) and not 'Mock' in type(pos_magic).__name__:
                magic_number = int(pos_magic)
        close_all_open_positions("BASKET_TP", symbol=current_symbol, magic=magic_number)
        return True
    return False

def check_and_trigger_entry(h1_row, m1_df, m5_df, tick):
    """Checks entry conditions and opens the first position of the layer."""
    h1_signal = check_h1_signal(h1_row)
    if h1_signal is None:
        return None
        
    # Check M5 crossover entry first (for all symbols)
    m5_cross = check_timeframe_crossover(m5_df, "M5")
    if h1_signal == m5_cross:
        price = tick.ask if h1_signal == "BUY" else tick.bid
        logger.info(f"[ENTRY] Trend ({h1_signal}) and M5 RSI crossover aligned. Opening Layer 1 at {price:.2f}")
        magic_number = getattr(btc_config, "MAGIC_NUMBER_M5", btc_config.MAGIC_NUMBER)
        ticket = open_trade(h1_signal, price, 0.0, 0.0, magic=magic_number)
        if ticket:
            return {
                "direction": h1_signal,
                "first_entry_price": price,
                "total_layers": 1
            }
            
    # Check M1 crossover entry (except XAGUSD)
    is_xagusd = "XAGUSD" in btc_config.SYMBOL
    logger.info(f"[{btc_config.SYMBOL}]Check M1, is_xagusd: {is_xagusd}")
    if not is_xagusd:
        m1_cross = check_timeframe_crossover(m1_df, "M1")
        if h1_signal == m1_cross:
            price = tick.ask if h1_signal == "BUY" else tick.bid
            logger.info(f"[ENTRY] Trend ({h1_signal}) and M1 RSI crossover aligned. Opening Layer 1 at {price:.2f}")
            magic_number = btc_config.MAGIC_NUMBER
            ticket = open_trade(h1_signal, price, 0.0, 0.0, magic=magic_number)
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
    """Fetches and calculates H1, M1, and M5 indicators."""
    h1_rates = mt5.copy_rates_from_pos(btc_config.SYMBOL, mt5.TIMEFRAME_H1, 0, 300)
    m1_rates = mt5.copy_rates_from_pos(btc_config.SYMBOL, mt5.TIMEFRAME_M1, 0, 100)
    m5_rates = mt5.copy_rates_from_pos(btc_config.SYMBOL, mt5.TIMEFRAME_M5, 0, 100)
    if h1_rates is None or m1_rates is None or m5_rates is None:
        return None, None, None
    h1_df = calculate_h1_layer_indicators(rates_to_df(h1_rates))
    m1_df = calculate_m1_layer_indicators(rates_to_df(m1_rates))
    m5_df = calculate_m1_layer_indicators(rates_to_df(m5_rates))
    return h1_df, m1_df, m5_df

def is_spread_valid(tick):
    """Checks if current spread is within allowed limits."""
    spread = tick.ask - tick.bid
    if spread > btc_config.MAX_SPREAD_USD:
        logger.warning(f"Spread {spread:.2f} exceeds limit {btc_config.MAX_SPREAD_USD:.2f}.")
        return False
    return True

def process_loop_logic(positions, state, h1_df, m1_df, m5_df, h1_row, tick, loop_state, starting_balance):
    """Processes entry, layering, take profit, and exit checks for a loop iteration."""
    if positions:
        if handle_basket_tp(positions, state):
            return None
        step = get_layer_step(h1_row)
        handle_layering(positions, state, step, tick)
        
        is_m1_active = positions[0].magic == btc_config.MAGIC_NUMBER
        active_df = m1_df if is_m1_active else m5_df
        completed_time = active_df.iloc[-2]['time']
        
        time_key = "last_m1_time" if is_m1_active else "last_m5_time"
        if loop_state.get(time_key) is None or completed_time > loop_state[time_key]:
            loop_state[time_key] = completed_time
            total_profit = sum(p.profit + p.swap for p in positions)
            offset = state["total_layers"] * step
            trigger = state["first_entry_price"] - offset if state["direction"] == "BUY" else state["first_entry_price"] + offset
            logger.info(f"[Basket Log] Layers: {state['total_layers']} | Net Profit: {total_profit:.2f} USD (Target TP: {btc_config.TAKE_PROFIT_PER_LAYER_USD * state['total_layers']:.2f} USD) | Next Trigger: {trigger:.2f}")
            
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
        completed_m5_time = m5_df.iloc[-2]['time']
        
        m1_new = loop_state.get("last_m1_time") is None or completed_m1_time > loop_state["last_m1_time"]
        m5_new = loop_state.get("last_m5_time") is None or completed_m5_time > loop_state["last_m5_time"]
        
        if m1_new or m5_new:
            if m1_new:
                loop_state["last_m1_time"] = completed_m1_time
            if m5_new:
                loop_state["last_m5_time"] = completed_m5_time
            state = check_and_trigger_entry(h1_row, m1_df, m5_df, tick)
            
    return state

def run_trading_loop(symbol, starting_balance, stop_event):
    """Orchestrates layering strategy checking tick data and completed candles."""
    btc_config.set_active_symbol(symbol)
    logger.info(f"[{symbol}] Entering trading loop...")
    loop_state = {"last_h1_time": None, "last_m1_time": None}
    state = None
    while not stop_event.is_set():
        try:
            btc_config.set_active_symbol(symbol)
            tick = mt5.symbol_info_tick(symbol)
            raw_positions = mt5.positions_get(symbol=symbol)
            m1_magic = btc_config.MAGIC_NUMBER
            m5_magic = getattr(btc_config, "MAGIC_NUMBER_M5", None)
            
            m1_positions = [p for p in raw_positions if p.magic == m1_magic] if raw_positions else []
            m5_positions = [p for p in raw_positions if p.magic == m5_magic] if raw_positions and m5_magic else []
            
            if m5_positions:
                positions = m5_positions
                magic_number = m5_magic
            elif m1_positions:
                positions = m1_positions
                magic_number = m1_magic
            else:
                positions = []
                magic_number = m5_magic if m5_magic is not None else m1_magic
            
            if positions:
                threshold = btc_config.number_of_normal_layer * btc_config.constant
                if len(positions) > threshold:
                    logger.warning(
                        f"[{symbol}] Open positions ({len(positions)}) exceeded threshold ({threshold}). "
                        f"Closing all positions."
                    )
                    close_all_open_positions("Layer Limit Exceeded", symbol=symbol, magic=magic_number)
                    positions = []
            if not positions:
                state = None
            elif state is None:
                state = recover_layer_state(positions)
            # if tick and is_spread_valid(tick):
            if tick:
                h1_df, m1_df, m5_df = fetch_indicators_data()
                if h1_df is not None and m1_df is not None and m5_df is not None:
                    h1_row = h1_df.iloc[-2]
                    state = process_loop_logic(positions, state, h1_df, m1_df, m5_df, h1_row, tick, loop_state, starting_balance)
        except Exception as e:
            logger.error(f"[{symbol}] Error in loop: {e}", exc_info=True)
        time.sleep(20)
    
    logger.info(f"[{symbol}] Exiting trading loop (keeping open positions).")

def main():
    import argparse
    from config.credentials import get_mt5_credentials
    
    credentials = get_mt5_credentials()
    # default_symbol = credentials.get("symbol", "BTCUSDc,XAUUSDc")
    default_symbol = credentials.get("symbol", "BTCUSDc")
    
    parser = argparse.ArgumentParser(description="BTC Layer Trading Bot")
    parser.add_argument("--symbol", type=str, default=default_symbol, help="Symbol(s) to trade (comma-separated or 'all')")
    args = parser.parse_args()
    
    # Resolve symbols list
    if args.symbol.lower() == "all":
        symbols = btc_config.ACTIVE_SYMBOLS
    else:
        symbols = [s.strip() for s in args.symbol.split(",") if s.strip()]
        
    if not symbols:
        logger.error("No valid symbols specified.")
        sys.exit(1)
        
    # Set the first symbol as active for MT5 initialization
    btc_config.set_active_symbol(symbols[0])
    initialize_mt5()
    
    # Select all other symbols in MT5
    for sym in symbols:
        if not mt5.symbol_select(sym, True):
            logger.error(f"Symbol {sym} select failed.")
            mt5.shutdown()
            sys.exit(1)
            
    account_info = mt5.account_info()
    if not account_info:
        logger.error("Failed to get MT5 account info.")
        mt5.shutdown()
        sys.exit(1)
        
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    starting_balance = account_info.balance - get_daily_realized_profit(today)
    
    stop_event = threading.Event()
    threads = []
    for sym in symbols:
        t = threading.Thread(target=run_trading_loop, args=(sym, starting_balance, stop_event), name=f"Thread-{sym}")
        t.start()
        threads.append(t)
        time.sleep(0.5) # Stagger start slightly
        
    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        logger.info("Shutdown requested. Signaling threads to exit...")
        stop_event.set()
        
    for t in threads:
        t.join()
        
    mt5.shutdown()
    logger.info("Shutdown complete.")

if __name__ == "__main__":
    main()
