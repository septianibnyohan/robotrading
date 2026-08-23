import os
import sys
import json
import time
import argparse
import logging
import threading
import signal
from datetime import datetime, timezone
import MetaTrader5 as mt5
import types
from functools import wraps

mt5_lock = threading.RLock()

def make_thread_safe(func):
    @wraps(func)
    def wrapper(*args_fn, **kwargs_fn):
        with mt5_lock:
            func_name = getattr(func, "__name__", "")
            if func_name in ("initialize", "last_error"):
                if not kwargs_fn:
                    return func(*args_fn)
                return func(*args_fn, **kwargs_fn)
                
            if not kwargs_fn:
                res = func(*args_fn)
            else:
                res = func(*args_fn, **kwargs_fn)
                
            if res is None:
                err = mt5.last_error()
                if err and (err[0] in (-10001, -10002, -10003, -10004) or "IPC" in str(err[1])):
                    try:
                        # Attempt to dynamically reconnect
                        reinit = mt5.initialize(
                            path=args.path,
                            login=args.login,
                            password=args.password,
                            server=args.server
                        )
                        if reinit:
                            # Retry the original call
                            if not kwargs_fn:
                                res = func(*args_fn)
                            else:
                                res = func(*args_fn, **kwargs_fn)
                    except Exception:
                        pass
            return res
    return wrapper

# Wrap all functions in mt5 module to make them thread-safe
for attr_name in dir(mt5):
    attr = getattr(mt5, attr_name)
    if isinstance(attr, (types.FunctionType, types.BuiltinFunctionType, types.MethodType)) and not attr_name.startswith("__"):
        setattr(mt5, attr_name, make_thread_safe(attr))

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Parse CLI Arguments
parser = argparse.ArgumentParser(description="Isolated MT5 Live Account Runner")
parser.add_argument("--login", type=int, required=True, help="MT5 Account Login")
parser.add_argument("--password", type=str, required=True, help="MT5 Account Password")
parser.add_argument("--server", type=str, required=True, help="MT5 Account Server")
parser.add_argument("--path", type=str, required=True, help="Path to terminal64.exe")
parser.add_argument("--symbols", type=str, required=True, help="Comma-separated symbols list")
args = parser.parse_args()

login = args.login
password = args.password
server = args.server
path = args.path
symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]

# Create required directories
os.makedirs("data/sessions", exist_ok=True)
os.makedirs("data/logs", exist_ok=True)

# Configure logging to write to account-specific log file and stdout
import logging.handlers
log_path = f"data/logs/{login}.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] " + f"({login}) %(message)s",
    handlers=[
        logging.handlers.RotatingFileHandler(log_path, encoding='utf-8', maxBytes=5 * 1024 * 1024, backupCount=1),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(f"account_runner_{login}")

# Import local strategy modules
import btc_config
import btc_layer_bot
from btc_risk import get_daily_realized_profit

# Active State tracking
stop_events = {}
threads = {}
is_running = True

def handle_shutdown(signum, frame):
    global is_running
    logger.info("Termination signal received. Shutting down trading loops...")
    is_running = False
    
    # Set all stop events
    for sym, stop_event in stop_events.items():
        stop_event.set()
        
    # Join all threads
    for sym, t in threads.items():
        t.join(timeout=2.0)
        logger.info(f"Thread for {sym} stopped.")
        
    try:
        mt5.shutdown()
        logger.info("MetaTrader5 connection shut down.")
    except:
        pass
    logger.info("Account runner process exited cleanly.")
    sys.exit(0)

# Register shutdown signals
signal.signal(signal.SIGINT, handle_shutdown)
signal.signal(signal.SIGTERM, handle_shutdown)

def write_session_data():
    try:
        acc_info = mt5.account_info()
        if not acc_info:
            return
            
        # Account details
        acc_dict = {
            "balance": round(acc_info.balance, 2),
            "equity": round(acc_info.equity, 2),
            "margin_free": round(acc_info.margin_free, 2),
            "profit": round(acc_info.profit, 2),
            "login": acc_info.login,
            "server": acc_info.server,
            "currency": acc_info.currency
        }
        
        # Sessions details
        active_sessions = []
        for sym in symbols:
            positions = mt5.positions_get(symbol=sym)
            layers = len(positions) if positions else 0
            direction = None
            first_entry_price = 0.0
            net_profit = 0.0
            
            if positions:
                oldest = min(positions, key=lambda p: p.time)
                direction = "BUY" if oldest.type == mt5.POSITION_TYPE_BUY else "SELL"
                first_entry_price = oldest.price_open
                net_profit = sum(p.profit + p.swap for p in positions)
            
            tick = mt5.symbol_info_tick(sym)
            current_price = 0.0
            if tick:
                current_price = tick.bid if direction == "BUY" else tick.ask
                if not direction:
                    current_price = (tick.bid + tick.ask) / 2
                    
            btc_config.set_active_symbol(sym)
            active_sessions.append({
                "symbol": sym,
                "layers": layers,
                "direction": direction,
                "first_entry_price": first_entry_price,
                "net_profit": round(net_profit, 2),
                "risk_level": btc_config.get_risk_level(),
                "current_price": current_price
            })
            
        status = {
            "bot_running": True,
            "running_symbols": symbols,
            "active_sessions": active_sessions,
            "account": acc_dict,
            "last_updated": time.time()
        }
        
        # Dump to status file
        status_path = f"data/sessions/{login}_status.json"
        with open(status_path, "w") as f:
            json.dump(status, f, indent=2)

        # Dump positions list to positions file
        raw_positions = mt5.positions_get()
        serialized_positions = []
        if raw_positions:
            for p in raw_positions:
                serialized_positions.append({
                    "ticket": p.ticket,
                    "symbol": p.symbol,
                    "type": "BUY" if p.type == mt5.POSITION_TYPE_BUY else "SELL",
                    "volume": p.volume,
                    "price_open": p.price_open,
                    "magic": p.magic,
                    "sl": p.sl,
                    "tp": p.tp,
                    "time": p.time,
                    "profit": round(p.profit, 2),
                    "swap": round(p.swap, 2)
                })
        positions_path = f"data/sessions/{login}_positions.json"
        with open(positions_path, "w") as f:
            json.dump(serialized_positions, f, indent=2)
            
    except Exception as e:
        logger.error(f"Error compiling session status data: {e}")

def dump_deals_history():
    try:
        now = int(time.time())
        start_time = now - 30 * 86400
        deals = mt5.history_deals_get(start_time, now + 10)
        
        history = []
        acc_info = mt5.account_info()
        current_balance = acc_info.balance if acc_info else 0.0

        if deals:
            sorted_deals = sorted(list(deals), key=lambda x: x.time)
            closed_deals = [d for d in sorted_deals if d.entry == mt5.DEAL_ENTRY_OUT]
            
            if closed_deals:
                total_profit = sum(d.profit + d.swap for d in closed_deals)
                initial_balance = current_balance - total_profit
                
                running_balance = initial_balance
                history.append({
                    "time": datetime.fromtimestamp(start_time, tz=timezone.utc).isoformat(),
                    "balance": round(initial_balance, 2),
                    "profit": 0.0,
                    "reason": "Initial",
                    "symbol": ""
                })
                
                for d in closed_deals:
                    running_balance += d.profit + d.swap
                    dt = datetime.fromtimestamp(d.time, tz=timezone.utc)
                    history.append({
                        "time": dt.isoformat(),
                        "balance": round(running_balance, 2),
                        "profit": round(d.profit, 2),
                        "reason": d.comment or f"Reason {d.reason}",
                        "symbol": d.symbol,
                        "ticket": d.ticket
                    })

        if len(history) < 2:
            history = []
            history.append({
                "time": datetime.fromtimestamp(start_time, tz=timezone.utc).isoformat(),
                "balance": round(current_balance, 2),
                "profit": 0.0,
                "reason": "Initial",
                "symbol": ""
            })
            history.append({
                "time": datetime.fromtimestamp(now, tz=timezone.utc).isoformat(),
                "balance": round(current_balance, 2),
                "profit": 0.0,
                "reason": "Current",
                "symbol": ""
            })
                
        history_path = f"data/sessions/{login}_history.json"
        with open(history_path, "w") as f:
            json.dump(history, f, indent=2)
            
    except Exception as e:
        logger.error(f"Error dumping closed deals history: {e}")

def main():
    # Pre-launch the MT5 terminal to enforce portable mode isolation if it is in a custom path
    if "Program Files" not in path:
        logger.info(f"Pre-launching MT5 in portable mode to prevent socket clashing: {path} /portable")
        try:
            import shutil
            src_dir = r"C:\Users\septi\AppData\Roaming\MetaQuotes\Terminal\9E1962F504DD205630274C46543BC64F\config"
            dst_dir = os.path.join(os.path.dirname(path), "config")
            if os.path.exists(src_dir) and os.path.exists(dst_dir):
                shutil.copy2(os.path.join(src_dir, "servers.dat"), os.path.join(dst_dir, "servers.dat"))
                shutil.copy2(os.path.join(src_dir, "accounts.dat"), os.path.join(dst_dir, "accounts.dat"))
                logger.info("Cloned server and account configurations to portable terminal config folder.")
        except Exception as e:
            logger.error(f"Failed to clone configurations: {e}")
            
        try:
            import subprocess
            subprocess.Popen([path, "/portable"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(3.0)
        except Exception as e:
            logger.error(f"Failed to pre-launch MT5 in portable mode: {e}")

    logger.info(f"Initializing connection to MT5 terminal at: {path}")
    
    # Initialize connection
    if not mt5.initialize(path=path, login=login, password=password, server=server):
        logger.error(f"Failed to initialize MT5 connection: {mt5.last_error()}")
        sys.exit(1)
        
    logger.info("Successfully connected to MT5 account.")
    
    # Wait for terminal to complete broker server authorization
    acc_info = None
    for attempt in range(15):
        acc_info = mt5.account_info()
        if acc_info is not None:
            break
        logger.info(f"Waiting for MT5 account authorization (attempt {attempt+1}/15)...")
        time.sleep(1.0)
        
    if not acc_info:
        logger.error("Failed to retrieve MT5 account info (authorization timeout).")
        sys.exit(1)
        
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    starting_balance = acc_info.balance - get_daily_realized_profit(today)
    
    logger.info(f"Starting balance calculated: {starting_balance} USD (daily realized profit deducted).")
    
    # Start bot threads
    for sym in symbols:
        logger.info(f"Starting trading loop thread for {sym}...")
        mt5.symbol_select(sym, True)
        
        stop_event = threading.Event()
        stop_events[sym] = stop_event
        
        t = threading.Thread(
            target=btc_layer_bot.run_trading_loop,
            args=(sym, starting_balance, stop_event),
            name=f"RunnerThread-{login}-{sym}"
        )
        t.daemon = True
        t.start()
        threads[sym] = t
        
    logger.info(f"All {len(symbols)} trading threads started successfully.")
    
    # Main reporting loop
    history_counter = 0
    while is_running:
        # Check for emergency close flag file
        close_flag_path = f"data/sessions/{login}_close_all.flag"
        if os.path.exists(close_flag_path):
            logger.warning("Emergency close flag detected! Closing all open positions...")
            try:
                import btc_trading
                for sym in symbols:
                    btc_config.set_active_symbol(sym)
                    magics = [
                        getattr(btc_config, 'MAGIC_NUMBER', 20260523),
                        getattr(btc_config, 'MAGIC_NUMBER_M5', None),
                        getattr(btc_config, 'MAGIC_NUMBER_M15', None)
                    ]
                    for magic in magics:
                        if magic is not None:
                            btc_trading.close_all_open_positions("GUI Emergency Close", symbol=sym, magic=magic)
            except Exception as ex:
                logger.error(f"Error executing emergency close from flag: {ex}")
            finally:
                try:
                    os.remove(close_flag_path)
                except:
                    pass

        write_session_data()
        
        # Dump history every 10 seconds to limit disk I/O
        history_counter += 1
        if history_counter >= 5:
            dump_deals_history()
            history_counter = 0
            
        time.sleep(2)

if __name__ == "__main__":
    main()
