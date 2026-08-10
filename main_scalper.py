import time
import os
import sys
import argparse
import logging
from datetime import datetime, timezone, timedelta
import pandas as pd
import MetaTrader5 as mt5

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.mt5_bridge import MT5Bridge
from monitoring.logger import setup_logging
from config.credentials import get_mt5_credentials
from execution.executor import TradeExecutor
from strategies.rsi_ema_50_cross_scalper import RsiEma50CrossScalperStrategy
from utils.news_filter import NewsFilter
from utils.signal_logger import SignalLogger
from utils.telegram import TelegramNotifier


# Import winsound for Windows beep
try:
    import winsound
except ImportError:
    winsound = None

# Audio alert functions
def trigger_audio_alert(side, symbol=""):
    """
    Triggers a beep and uses Windows TTS to say the action.
    """
    # 1. Beep sound
    if winsound:
        try:
            # Frequency: 1000Hz for Buy, 600Hz for Sell. Duration: 300ms.
            frequency = 1000 if side.lower() == "buy" else 600
            winsound.Beep(frequency, 300)
        except Exception:
            pass
            
    # 2. Text-to-Speech via PowerShell
    try:
        import subprocess
        asset = "Silver" if "XAG" in symbol else ("Gold" if "XAU" in symbol else ("ETH" if "ETH" in symbol else "BTC"))
        msg = f"{side.upper()} {asset} trade triggered"
        # Run PowerShell asynchronously to prevent blocking the main loop
        subprocess.Popen([
            "powershell", 
            "-Command", 
            f"Add-Type -AssemblyName System.Speech; (New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak('{msg}');"
        ])
    except Exception:
        pass

def check_cooldown(symbol, timeframe_minutes, current_bar_time, logger):
    """
    Checks if we are in a cooldown period after a Stop Loss exit.
    Returns (is_cooldown_active, last_sl_time).
    """
    # Query deals for the last 24 hours
    now_ts = int(time.time())
    start_ts = now_ts - 86400
    
    deals = mt5.history_deals_get(start_ts, now_ts + 10)
    if deals is None or len(deals) == 0:
        return False, None
        
    # Filter for closing deals on our symbol
    closed_deals = [d for d in deals if d.symbol == symbol and d.entry == mt5.DEAL_ENTRY_OUT]
    if not closed_deals:
        return False, None
        
    # Sort by execution time to get the most recent one
    closed_deals.sort(key=lambda x: x.time)
    last_deal = closed_deals[-1]
    
    # Check if the reason was Stop Loss (reason = 3 / mt5.DEAL_REASON_SL)
    # Or check if "sl" is in the comment as fallback
    is_sl = (last_deal.reason == 3) or ("sl" in last_deal.comment.lower())
    
    if is_sl:
        timeframe_seconds = timeframe_minutes * 60
        deal_bar_time = (last_deal.time // timeframe_seconds) * timeframe_seconds
        
        # Cooldown lasts 3 candles. So we wait for:
        # Deal candle, deal candle+1, deal+2, deal+3 to complete.
        # We can enter on deal candle + 4.
        cooldown_until = deal_bar_time + 4 * timeframe_seconds
        current_bar_ts = int(current_bar_time.timestamp())
        
        if current_bar_ts < cooldown_until:
            wait_seconds = cooldown_until - current_bar_ts
            wait_candles = int(wait_seconds / timeframe_seconds)
            logger.info(f"Cooldown ACTIVE. Last SL deal at {datetime.fromtimestamp(last_deal.time, tz=timezone.utc)}. "
                        f"Wait {wait_candles} more candles.")
            return True, last_deal.time
            
    return False, None

def main():
    # Two-pass parsing: first parse only '--symbol' to initialize configuration
    temp_parser = argparse.ArgumentParser(add_help=False)
    temp_parser.add_argument("--symbol", type=str, default=None)
    temp_args, _ = temp_parser.parse_known_args()
    
    # Resolve active symbol
    import btc_config
    if temp_args.symbol:
        btc_config.set_active_symbol(temp_args.symbol)
    else:
        credentials = get_mt5_credentials()
        btc_config.set_active_symbol(credentials.get("symbol", "XAUUSDc"))
        
    symbol = btc_config.SYMBOL

    is_gold = symbol.startswith("XAU")
    is_silver = symbol.startswith("XAG")
    default_spread = int(getattr(btc_config, "MAX_SPREAD_USD", 2.5) * 10) if is_gold else (int(getattr(btc_config, "MAX_SPREAD_USD", 0.05) * 1000) if is_silver else int(getattr(btc_config, "MAX_SPREAD_USD", 15)))

    parser = argparse.ArgumentParser(description="EMA+RSI(7) 50-Cross Scalper")
    parser.add_argument("--symbol", type=str, default=symbol, help="Symbol to trade")
    parser.add_argument("--fast-ema", type=int, default=getattr(btc_config, "EMA_FAST", 5), help="Fast EMA period")
    parser.add_argument("--slow-ema", type=int, default=getattr(btc_config, "EMA_SLOW", 13), help="Slow EMA period")
    parser.add_argument("--rsi-period", type=int, default=getattr(btc_config, "RSI_PERIOD", 7), help="RSI period")
    parser.add_argument("--rsi-level", type=float, default=50.0, help="RSI crossing level")
    parser.add_argument("--min-atr", type=float, default=0.8, help="Min ATR(14) to filter flat markets")
    parser.add_argument("--max-spread", type=int, default=default_spread, help="Max spread")
    parser.add_argument("--use-news", type=bool, default=True, help="Block trades around news")
    parser.add_argument("--rr", type=float, default=1.5, help="Risk Reward ratio")
    parser.add_argument("--fixed-sl-pips", type=float, default=5.0, help="Fixed stop loss in pips if ATR not used")
    parser.add_argument("--use-atr-sl", type=bool, default=True, help="Use ATR based stop loss")
    parser.add_argument("--max-hold-min", type=int, default=10, help="Max position holding time in minutes")
    parser.add_argument("--lot-size", type=float, default=getattr(btc_config, "LOT_SIZE", 0.01), help="Position volume")
    parser.add_argument("--use-trail", type=bool, default=True, help="Use trailing stop")
    parser.add_argument("--timeframe", type=str, default="M1", choices=["M1", "M5"], help="Primary timeframe")
    
    args = parser.parse_args()
    
    logger = setup_logging()
    logger.info(f"Initializing {symbol} EMA+RSI 50-Cross Scalper...")
    
    # 1. MT5 Connection
    bridge = MT5Bridge()
    if not bridge.connect():
        logger.error("Could not connect to MT5. Exiting.")
        return

    # Get digits dynamically for rounding and formatting
    info = mt5.symbol_info(symbol)
    digits = info.digits if info is not None else (5 if "EURUSD" in symbol else 2)
        
    logger.info(f"Bot started. Instrument: {symbol} | Timeframe: {args.timeframe}")
    logger.info(f"Parameters: Fast EMA={args.fast_ema}, Slow EMA={args.slow_ema}, RSI={args.rsi_period}, "
                f"Min ATR={args.min_atr}, Max Spread={args.max_spread}, Use ATR SL={args.use_atr_sl}, "
                f"Fixed SL={args.fixed_sl_pips} pips, Max Hold={args.max_hold_min}m, Lot={args.lot_size}")
    
    # 2. Objects Initialization
    executor = TradeExecutor(symbol)
    strategy = RsiEma50CrossScalperStrategy(
        fast_ema_period=args.fast_ema,
        slow_ema_period=args.slow_ema,
        rsi_period=args.rsi_period,
        rsi_level=args.rsi_level,
        min_atr=args.min_atr
    )
    news_filter = NewsFilter(use_news_filter=args.use_news)
    sig_logger = SignalLogger()
    notifier = TelegramNotifier()
    
    tf_const = mt5.TIMEFRAME_M1 if args.timeframe == "M1" else mt5.TIMEFRAME_M5
    tf_minutes = 1 if args.timeframe == "M1" else 5
    pip_size = 0.01 if "XAGUSD" in symbol else 0.10
    
    last_trade_bar = None
    last_notified_rsi_cross_time = None
    
    try:
        while True:
            # Watchdog check
            bridge.ensure_connection()
            
            # 3. Retrieve Rates
            # Fetch 250 bars. Position 0 is current forming bar, index 249 is latest.
            rates = mt5.copy_rates_from_pos(symbol, tf_const, 0, 250)
            if rates is None or len(rates) < 50:
                logger.warning("Failed to fetch rates or insufficient history.")
                time.sleep(2.0)
                continue
                
            df = pd.DataFrame(rates)
            df['time'] = pd.to_datetime(df['time'], unit='s')
            
            # Separate completed candles from the currently active forming candle (the last row)
            df_completed = df.iloc[:-1].copy()
            current_bar = df.iloc[-1]
            
            # Generate signals on completed candles to guarantee NO repainting
            df_signals = strategy.generate_signals(df_completed)
            if df_signals.empty:
                time.sleep(2.0)
                continue

            # Check for RSI 50 crossover on completed candle
            forming_time = df.iloc[-1]['time']
            completed_df = df_signals[df_signals['time'] < forming_time]
            if not completed_df.empty:
                completed_row = completed_df.iloc[-1]
                completed_time = completed_row['time']
                
                if completed_time != last_notified_rsi_cross_time:
                    prev_rsi = completed_row['prev_rsi']
                    curr_rsi = completed_row['rsi']
                    
                    rsi_cross_up = (prev_rsi <= args.rsi_level) and (curr_rsi > args.rsi_level)
                    rsi_cross_down = (prev_rsi >= args.rsi_level) and (curr_rsi < args.rsi_level)
                    
                    if rsi_cross_up or rsi_cross_down:
                        direction = "UP" if rsi_cross_up else "DOWN"
                        
                        # Determine criteria matches
                        vol_ok = bool(completed_row.get('volatility_ok', True))
                        trend_ok = bool(completed_row.get('ema_trend_ok', True))
                        fast_gt_slow = bool(completed_row['fast_ema'] > completed_row['slow_ema'])
                        fast_lt_slow = bool(completed_row['fast_ema'] < completed_row['slow_ema'])
                        close_gt_fast = bool(completed_row['close'] > completed_row['fast_ema'])
                        close_lt_fast = bool(completed_row['close'] < completed_row['fast_ema'])
                        
                        msg = (
                            f"🔔 <b>RSI 50 Cross Detected ({direction})</b>\n"
                            f"<b>Time:</b> {completed_time}\n"
                            f"<b>Current Price:</b> {completed_row['close']:.{digits}f}\n"
                            f"<b>EMA Fast:</b> {completed_row['fast_ema']:.{digits}f}\n"
                            f"<b>EMA Slow:</b> {completed_row['slow_ema']:.{digits}f}\n"
                            f"<b>RSI Previous:</b> {prev_rsi:.2f}\n"
                            f"<b>RSI Current:</b> {curr_rsi:.2f}\n\n"
                            f"📈 <b>Long Criteria:</b>\n"
                            f"- Volatility OK: {'✅' if vol_ok else '❌'}\n"
                            f"- Trend OK: {'✅' if trend_ok else '❌'}\n"
                            f"- Fast EMA &gt; Slow EMA: {'✅' if fast_gt_slow else '❌'}\n"
                            f"- RSI Cross Up: {'✅' if rsi_cross_up else '❌'}\n"
                            f"- Close &gt; Fast EMA: {'✅' if close_gt_fast else '❌'}\n\n"
                            f"📉 <b>Short Criteria:</b>\n"
                            f"- Volatility OK: {'✅' if vol_ok else '❌'}\n"
                            f"- Trend OK: {'✅' if trend_ok else '❌'}\n"
                            f"- Fast EMA &lt; Slow EMA: {'✅' if fast_lt_slow else '❌'}\n"
                            f"- RSI Cross Down: {'✅' if rsi_cross_down else '❌'}\n"
                            f"- Close &lt; Fast EMA: {'✅' if close_lt_fast else '❌'}"
                        )
                        notifier.send_message(msg)
                        last_notified_rsi_cross_time = completed_time
                
            last_completed = df_signals.iloc[-1]
            last_completed_time = last_completed['time']
            
            # Get current bid/ask
            tick = mt5.symbol_info_tick(symbol)
            if tick is None:
                logger.warning("Failed to get current tick.")
                time.sleep(1.0)
                continue
                
            bid, ask = tick.bid, tick.ask
            point = mt5.symbol_info(symbol).point
            spread_points = (ask - bid) / point
            
            # 4. Open Positions Monitoring & Manage Exits
            positions = executor.get_open_positions()
            current_time = datetime.now(timezone.utc)
            long_exit_sig = bool(last_completed.get('long_exit', False))
            short_exit_sig = bool(last_completed.get('short_exit', False))
            closed_any = False
            
            for pos in positions:
                # Time Stop Check
                open_time = datetime.fromtimestamp(pos.time, tz=timezone.utc)
                elapsed_min = (current_time - open_time).total_seconds() / 60.0
                
                if elapsed_min >= args.max_hold_min:
                    logger.info(f"Time Stop hit for position {pos.ticket}. Holding time: {elapsed_min:.1f} mins.")
                    executor.close_position(pos)
                    sig_logger.log(
                        signal_type="EXIT_TIME_STOP",
                        price=bid if pos.type == mt5.POSITION_TYPE_BUY else ask,
                        spread=spread_points,
                        atr=last_completed['atr'],
                        status="executed"
                    )
                    closed_any = True
                    continue
                
                # Technical Exit Check
                if pos.type == mt5.POSITION_TYPE_BUY and long_exit_sig:
                    logger.info(f"Technical Long Exit triggered for position {pos.ticket}.")
                    executor.close_position(pos)
                    sig_logger.log(
                        signal_type="EXIT_LONG",
                        price=bid,
                        spread=spread_points,
                        atr=last_completed['atr'],
                        status="executed"
                    )
                    exit_msg = (
                        f"🚪 <b>Technical Long Exit Triggered</b>\n"
                        f"<b>Ticket:</b> {pos.ticket}\n"
                        f"<b>Price:</b> {bid:.{digits}f}\n"
                        f"<b>RSI:</b> {last_completed['rsi']:.2f}\n"
                        f"<b>EMA Fast:</b> {last_completed['fast_ema']:.{digits}f}\n"
                        f"<b>EMA Slow:</b> {last_completed['slow_ema']:.{digits}f}"
                    )
                    notifier.send_message(exit_msg)
                    closed_any = True
                    continue
                    
                if pos.type == mt5.POSITION_TYPE_SELL and short_exit_sig:
                    logger.info(f"Technical Short Exit triggered for position {pos.ticket}.")
                    executor.close_position(pos)
                    sig_logger.log(
                        signal_type="EXIT_SHORT",
                        price=ask,
                        spread=spread_points,
                        atr=last_completed['atr'],
                        status="executed"
                    )
                    exit_msg = (
                        f"🚪 <b>Technical Short Exit Triggered</b>\n"
                        f"<b>Ticket:</b> {pos.ticket}\n"
                        f"<b>Price:</b> {ask:.{digits}f}\n"
                        f"<b>RSI:</b> {last_completed['rsi']:.2f}\n"
                        f"<b>EMA Fast:</b> {last_completed['fast_ema']:.{digits}f}\n"
                        f"<b>EMA Slow:</b> {last_completed['slow_ema']:.{digits}f}"
                    )
                    notifier.send_message(exit_msg)
                    closed_any = True
                    continue

                # Trailing Stop Check
                if args.use_trail and pos.sl > 0:
                    # Calculate initial SL distance in price units
                    initial_sl_dist = abs(pos.price_open - pos.sl)
                    
                    if pos.type == mt5.POSITION_TYPE_BUY:
                        price_move = bid - pos.price_open
                        if price_move >= 2.0 * initial_sl_dist:
                            new_sl = bid - 0.5 * initial_sl_dist
                            # Round to point digits
                            new_sl = round(new_sl, digits)
                            if new_sl > pos.sl:
                                logger.info(f"Trailing Stop Buy: Moving SL from {pos.sl:.{digits}f} to {new_sl:.{digits}f}")
                                executor.modify_position_sltp(pos.ticket, new_sl, pos.tp)
                    elif pos.type == mt5.POSITION_TYPE_SELL:
                        price_move = pos.price_open - ask
                        if price_move >= 2.0 * initial_sl_dist:
                            new_sl = ask + 0.5 * initial_sl_dist
                            new_sl = round(new_sl, digits)
                            if pos.sl == 0 or new_sl < pos.sl:
                                logger.info(f"Trailing Stop Sell: Moving SL from {pos.sl:.{digits}f} to {new_sl:.{digits}f}")
                                executor.modify_position_sltp(pos.ticket, new_sl, pos.tp)
            
            # Refresh position state if we closed any
            if closed_any:
                positions = executor.get_open_positions()

            # If we already have open positions, do not check entries
            if len(positions) > 0:
                time.sleep(1.0)
                continue
                
            # 5. Evaluate Entry Signals
            long_trigger = bool(last_completed['long_entry'])
            short_trigger = bool(last_completed['short_entry'])
            
            if (long_trigger or short_trigger) and last_completed_time != last_trade_bar:
                signal_type = "BUY" if long_trigger else "SELL"
                price = ask if long_trigger else bid
                atr_val = last_completed['atr']
                
                # Filter Checks
                # A. Cooldown Filter
                is_cooldown, _ = check_cooldown(symbol, tf_minutes, last_completed_time, logger)
                if is_cooldown:
                    sig_logger.log(signal_type, price, spread_points, atr_val, "rejected", "cooldown active")
                    last_trade_bar = last_completed_time
                    continue
                    
                # B. News Filter
                # Check for high impact news within +/- 5 minutes
                utc_completed_time = last_completed_time.replace(tzinfo=timezone.utc)
                if news_filter.is_news_embargo(utc_completed_time, window_minutes=5):
                    logger.warning(f"Trade rejected: news embargo active for {utc_completed_time}")
                    sig_logger.log(signal_type, price, spread_points, atr_val, "rejected", "news embargo")
                    last_trade_bar = last_completed_time
                    continue
                    
                # C. Spread Filter
                if spread_points > args.max_spread:
                    logger.warning(f"Trade rejected: spread ({spread_points:.1f}) > max ({args.max_spread})")
                    sig_logger.log(signal_type, price, spread_points, atr_val, "rejected", "spread > max")
                    last_trade_bar = last_completed_time
                    continue
                
                # Technical filters already applied inside strategy (volatility_ok, ema_trend_ok)
                # But let's log if they failed just in case
                if not last_completed['volatility_ok']:
                    sig_logger.log(signal_type, price, spread_points, atr_val, "rejected", "low volatility")
                    last_trade_bar = last_completed_time
                    continue
                    
                if not last_completed['ema_trend_ok']:
                    sig_logger.log(signal_type, price, spread_points, atr_val, "rejected", "flat market")
                    last_trade_bar = last_completed_time
                    continue
                
                # Calculate SL and TP levels
                if args.use_atr_sl:
                    sl_dist = atr_val * 1.5
                else:
                    sl_dist = args.fixed_sl_pips * pip_size
                    
                tp_dist = sl_dist * args.rr
                # Cap TP at 15 pips (1.50 USD)
                max_tp_dist = 15.0 * pip_size
                if tp_dist > max_tp_dist:
                    tp_dist = max_tp_dist
                    
                if long_trigger:
                    sl_level = ask - sl_dist
                    tp_level = ask + tp_dist
                    logger.info(f"Executing BUY: Entry={ask:.{digits}f}, SL={sl_level:.{digits}f}, TP={tp_level:.{digits}f}")
                    res = executor.execute_buy(args.lot_size, stop_loss=round(sl_level, digits), take_profit=round(tp_level, digits))
                else:
                    sl_level = bid + sl_dist
                    tp_level = bid - tp_dist
                    logger.info(f"Executing SELL: Entry={bid:.{digits}f}, SL={sl_level:.{digits}f}, TP={tp_level:.{digits}f}")
                    res = executor.execute_sell(args.lot_size, stop_loss=round(sl_level, digits), take_profit=round(tp_level, digits))
                    
                if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                    logger.info(f"Trade successfully placed! Ticket: {res.order}")
                    sig_logger.log(signal_type, price, spread_points, atr_val, "executed")
                    trigger_audio_alert(signal_type, symbol)
                    last_trade_bar = last_completed_time
                else:
                    reason = res.comment if res else "unknown error"
                    logger.error(f"Trade execution failed: {reason}")
                    sig_logger.log(signal_type, price, spread_points, atr_val, "failed", reason)
            
            time.sleep(0.5)
            
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")
    finally:
        bridge.disconnect()

if __name__ == "__main__":
    main()
