import sys
import time
import logging
import threading
from datetime import datetime, timezone
import MetaTrader5 as mt5

import btc_config
from btc_indicators import (
    calculate_m5_indicators, calculate_h1_indicators, 
    calculate_m15_indicators, fetch_rates, rates_to_df
)
from btc_risk import check_circuit_breaker, get_daily_realized_profit
from btc_trading import (
    initialize_mt5, open_trade, close_all_open_positions
)
from btc_exits import check_time_exit, handle_trailing_stop

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler("btc_m5_bot.log"), logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

def check_new_candle(last_time):
    """Detects closed M5 candle."""
    m5_rates = mt5.copy_rates_from_pos(btc_config.SYMBOL, mt5.TIMEFRAME_M5, 0, 500)
    if m5_rates is None or len(m5_rates) < btc_config.EMA_SLOW:
        return None, last_time
    df_m5 = rates_to_df(m5_rates)
    completed_time = df_m5.iloc[-2]['time']
    if last_time is None or completed_time > last_time:
        return df_m5, completed_time
    return None, last_time

def recover_trade_state(pos):
    """Recovers the trade state from the open position."""
    logger.info(f"Active position found upon startup: {pos.ticket}. Recovering trade state...")
    m5_rates = mt5.copy_rates_from_pos(btc_config.SYMBOL, mt5.TIMEFRAME_M5, 0, 100)
    atr = 100.0
    if m5_rates is not None and len(m5_rates) > 0:
        df = rates_to_df(m5_rates)
        df = calculate_m5_indicators(df)
        atr = df.iloc[-2]['atr_14']
    return {
        "entry_price": pos.price_open,
        "atr_at_entry": atr,
        "entry_time": pos.time,
        "peak_price": pos.price_open,
        "last_peak_time": pos.time,
        "trailing_active": False
    }

def check_long_conditions(m5_c, m5_p, h1_c, m15_c):
    """Evaluates and logs Long/Buy conditions."""
    logger.info(
        f"[VAL-LONG] close: {m5_c['close']:.2f}, ema_200: {m5_c['ema_200']:.2f}, "
        f"h1_slope: {h1_c['ema_50_slope']:.4f}, rsi: {m5_c['rsi_14']:.2f} (prev: {m5_p['rsi_14']:.2f}), "
        f"adx: {m5_c['adx_14']:.2f}, vol: {m5_c['tick_volume']} (ema: {m5_c['volume_ema_10']:.1f}), "
        f"ema_9: {m5_c['ema_9']:.2f}, m15_close: {m15_c['close']:.2f}, m15_ema_200: {m15_c['ema_200']:.2f}"
    )
    conds = {
        "price_gt_ema200": bool(m5_c['close'] > m5_c['ema_200']),
        "h1_slope_positive": bool(h1_c['ema_50_slope'] > 0),
        "rsi_gt_40": bool(m5_c['rsi_14'] > 40),
        "rsi_rising": bool(m5_c['rsi_14'] > m5_p['rsi_14']),
        "adx_gt_25": bool(m5_c['adx_14'] > 25),
        "volume_spike": bool(m5_c['tick_volume'] > m5_c['volume_ema_10'] * 1.5),
        "price_gt_ema9": bool(m5_c['close'] > m5_c['ema_9']),
        "m15_alignment": bool(m15_c['close'] > m15_c['ema_200'])
    }
    logger.info(f"[EVAL-LONG] {conds}")
    return all(conds.values())

def check_short_conditions(m5_c, m5_p, h1_c, m15_c):
    """Evaluates and logs Short/Sell conditions."""
    logger.info(
        f"[VAL-SHORT] close: {m5_c['close']:.2f}, ema_200: {m5_c['ema_200']:.2f}, "
        f"h1_slope: {h1_c['ema_50_slope']:.4f}, rsi: {m5_c['rsi_14']:.2f} (prev: {m5_p['rsi_14']:.2f}), "
        f"adx: {m5_c['adx_14']:.2f}, vol: {m5_c['tick_volume']} (ema: {m5_c['volume_ema_10']:.1f}), "
        f"ema_9: {m5_c['ema_9']:.2f}, m15_close: {m15_c['close']:.2f}, m15_ema_200: {m15_c['ema_200']:.2f}"
    )
    conds = {
        "price_lt_ema200": bool(m5_c['close'] < m5_c['ema_200']),
        "h1_slope_negative": bool(h1_c['ema_50_slope'] < 0),
        "rsi_lt_60": bool(m5_c['rsi_14'] < 60),
        "rsi_falling": bool(m5_c['rsi_14'] < m5_p['rsi_14']),
        "adx_gt_25": bool(m5_c['adx_14'] > 25),
        "volume_spike": bool(m5_c['tick_volume'] > m5_c['volume_ema_10'] * 1.5),
        "price_lt_ema9": bool(m5_c['close'] < m5_c['ema_9']),
        "m15_alignment": bool(m15_c['close'] < m15_c['ema_200'])
    }
    logger.info(f"[EVAL-SHORT] {conds}")
    return all(conds.values())

def check_entry_triggers(m5_c, m5_p, h1_c, m15_c, tick):
    """Checks criteria to generate entry states."""
    logger.info(f"Evaluating candle closed at {m5_c['time']}. Close Price: {m5_c['close']:.2f}")
    if check_long_conditions(m5_c, m5_p, h1_c, m15_c):
        return create_trade_state("BUY", tick.ask, m5_c['atr_14'], tick.time)
    if check_short_conditions(m5_c, m5_p, h1_c, m15_c):
        return create_trade_state("SELL", tick.bid, m5_c['atr_14'], tick.time)
    return None

def evaluate_and_execute(df_m5, tick, starting_balance):
    """Evaluates strategy and triggers trade."""
    is_ok, daily_pnl = check_circuit_breaker(starting_balance)
    if not is_ok:
        logger.info(f"Circuit Breaker active. Daily PnL: {daily_pnl:.2f} USD.")
        return None
    df_m5 = calculate_m5_indicators(df_m5)
    m5_comp, m5_prev = df_m5.iloc[-2], df_m5.iloc[-3]
    h1_comp = calculate_h1_indicators(fetch_rates(btc_config.SYMBOL, mt5.TIMEFRAME_H1, 100)).iloc[-2]
    m15_comp = calculate_m15_indicators(fetch_rates(btc_config.SYMBOL, mt5.TIMEFRAME_M15, 300)).iloc[-2]
    spread = tick.ask - tick.bid
    if spread > btc_config.MAX_SPREAD_USD:
        logger.warning(f"Spread {spread:.2f} exceeds limit {btc_config.MAX_SPREAD_USD:.2f}.")
        return None
    return check_entry_triggers(m5_comp, m5_prev, h1_comp, m15_comp, tick)

def create_trade_state(direction, price, atr, srv_time):
    """Constructs SL/TP and fires open order."""
    offset = atr * 1.5 if direction == "BUY" else -atr * 1.5
    sl = round(price - offset, 2)
    tp = round(price + (atr * 3.0 if direction == "BUY" else -atr * 3.0), 2)
    magic_number = getattr(btc_config, "MAGIC_NUMBER_M5", btc_config.MAGIC_NUMBER)
    ticket = open_trade(direction, price, sl, tp, magic=magic_number)
    if ticket:
        return {
            "entry_price": price, "atr_at_entry": atr, "entry_time": srv_time,
            "peak_price": price, "last_peak_time": srv_time, "trailing_active": False
        }
    return None

def run_trading_loop(symbol, starting_balance, stop_event):
    """Primary loop checking tickers and processing orders."""
    btc_config.set_active_symbol(symbol)
    last_time, state = None, None
    logger.info(f"[{symbol}] Entering trading loop...")
    while not stop_event.is_set():
        try:
            btc_config.set_active_symbol(symbol)
            tick = mt5.symbol_info_tick(symbol)
            raw_positions = mt5.positions_get(symbol=symbol)
            magic_number = getattr(btc_config, "MAGIC_NUMBER_M5", btc_config.MAGIC_NUMBER)
            positions = [p for p in raw_positions if p.magic == magic_number] if raw_positions else []
            if not positions:
                state = None
            if tick:
                if positions:
                    if state is None:
                        state = recover_trade_state(positions[0])
                    if not check_time_exit(positions[0], tick, state):
                        handle_trailing_stop(positions[0], tick, state)
                df_m5, last_time = check_new_candle(last_time)
                if df_m5 is not None and not positions:
                    state = evaluate_and_execute(df_m5, tick, starting_balance)
        except Exception as e:
            logger.error(f"[{symbol}] Error in loop: {e}", exc_info=True)
        time.sleep(5.0)
        
    logger.info(f"[{symbol}] Closing all positions...")
    magic_number = getattr(btc_config, "MAGIC_NUMBER_M5", btc_config.MAGIC_NUMBER)
    close_all_open_positions("Graceful Shutdown", symbol=symbol, magic=magic_number)

def main():
    import argparse
    from config.credentials import get_mt5_credentials
    
    credentials = get_mt5_credentials()
    default_symbol = credentials.get("symbol", "BTCUSDc,XAUUSDc")
    
    parser = argparse.ArgumentParser(description="BTC M5 Trading Bot")
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
