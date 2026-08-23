import os
import sys
import json
import time
import subprocess
import logging
import threading
import sqlite3
import contextvars
from datetime import datetime, timezone
import MetaTrader5 as mt5
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Define Context Variable for execution routing
trading_mode_var = contextvars.ContextVar('trading_mode', default="forward_test")

# Save original references before routing wrappers are applied
orig_positions_get = mt5.positions_get
orig_history_deals_get = mt5.history_deals_get
orig_account_info = mt5.account_info

import btc_trading
orig_open_trade = btc_trading.open_trade
orig_close_all_open_positions = btc_trading.close_all_open_positions

# Context-local routing wrapper functions
def route_positions_get(*args, **kwargs):
    mode = trading_mode_var.get()
    if mode == "forward_test" and bot_manager and bot_manager.sim_manager:
        return bot_manager.sim_manager.positions_get(*args, **kwargs)
    return orig_positions_get(*args, **kwargs)

def route_history_deals_get(*args, **kwargs):
    mode = trading_mode_var.get()
    if mode == "forward_test" and bot_manager and bot_manager.sim_manager:
        return bot_manager.sim_manager.history_deals_get(*args, **kwargs)
    return orig_history_deals_get(*args, **kwargs)

def route_account_info(*args, **kwargs):
    mode = trading_mode_var.get()
    if mode == "forward_test" and bot_manager and bot_manager.sim_manager:
        return bot_manager.sim_manager.account_info(*args, **kwargs)
    return orig_account_info(*args, **kwargs)

def route_open_trade(*args, **kwargs):
    mode = trading_mode_var.get()
    if mode == "forward_test" and bot_manager and bot_manager.sim_manager:
        return bot_manager.sim_manager.open_trade(*args, **kwargs)
    return orig_open_trade(*args, **kwargs)

def route_close_all_open_positions(*args, **kwargs):
    mode = trading_mode_var.get()
    if mode == "forward_test" and bot_manager and bot_manager.sim_manager:
        return bot_manager.sim_manager.close_all_open_positions(*args, **kwargs)
    return orig_close_all_open_positions(*args, **kwargs)

# Hook the routing interceptors globally
mt5.positions_get = route_positions_get
mt5.history_deals_get = route_history_deals_get
mt5.account_info = route_account_info
btc_trading.open_trade = route_open_trade
btc_trading.close_all_open_positions = route_close_all_open_positions

# Update main modules namespace
for mod_name in ['__main__', 'btc_layer_bot']:
    mod = sys.modules.get(mod_name)
    if mod:
        if hasattr(mod, 'open_trade'):
            mod.open_trade = route_open_trade
        if hasattr(mod, 'close_all_open_positions'):
            mod.close_all_open_positions = route_close_all_open_positions

# Load configurations and trading loop core
import btc_config
from core.mt5_bridge import MT5Bridge
from config.credentials import get_mt5_credentials
import btc_layer_bot
from core.simulator import ForwardTestManager

# Configure Logging
log_format = "%(asctime)s [%(levelname)s] %(message)s"
formatter = logging.Formatter(log_format)

stdout_handler = logging.StreamHandler(sys.stdout)
stdout_handler.setFormatter(formatter)

live_file_handler = logging.FileHandler("btc_layer_bot_live.log", encoding='utf-8', errors='ignore')
live_file_handler.setFormatter(formatter)

sim_file_handler = logging.FileHandler("btc_layer_bot_sim.log", encoding='utf-8', errors='ignore')
sim_file_handler.setFormatter(formatter)

class ModeRoutingHandler(logging.Handler):
    def __init__(self, live_h, sim_h):
        super().__init__()
        self.live_h = live_h
        self.sim_h = sim_h

    def emit(self, record):
        try:
            mode = trading_mode_var.get()
        except Exception:
            mode = "forward_test"
            
        if mode == "live":
            self.live_h.emit(record)
        else:
            self.sim_h.emit(record)

    def setFormatter(self, fmt):
        super().setFormatter(fmt)
        self.live_h.setFormatter(fmt)
        self.sim_h.setFormatter(fmt)

    def close(self):
        self.live_h.close()
        self.sim_h.close()
        super().close()

routing_handler = ModeRoutingHandler(live_file_handler, sim_file_handler)
routing_handler.setFormatter(formatter)

root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
for h in list(root_logger.handlers):
    root_logger.removeHandler(h)
root_logger.addHandler(stdout_handler)
root_logger.addHandler(routing_handler)

logger = logging.getLogger("web_server")

app = FastAPI(title="RoboBTC SaaS API", version="1.0.0")

# Enable CORS for React dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class BotManager:
    def __init__(self):
        self.bridge = MT5Bridge()
        self.mt5_connected = False
        
        # execution states separated by mode
        self.running_symbols = {"forward_test": []}
        self.stop_events = {"forward_test": {}}
        self.threads = {"forward_test": {}}
        
        # Live account subprocess dictionary: login -> Popen
        self.live_processes = {}
        
        # Instantiate forward test manager persistently
        self.sim_manager = ForwardTestManager()
        
        self.lock = threading.RLock()
        
        # Backtest state
        self.backtest_thread = None
        self.backtest_status = "idle"  # "idle" | "running" | "completed" | "error"
        self.backtest_results = None
        self.backtest_error = None

    def connect_mt5(self):
        with self.lock:
            if self.bridge.connect():
                self.mt5_connected = True
                logger.info("MT5 default connection established successfully (for market rate lookups).")
                return True
            else:
                self.mt5_connected = False
                logger.warning("MT5 default connection failed.")
                return False

    def get_status(self):
        # 1. Live Accounts details (from status files & active processes)
        accounts_list = []
        accounts = load_accounts()
        for acct in accounts:
            login_id = acct["login"]
            proc = self.live_processes.get(login_id)
            
            # Check if process is still running
            bot_running = False
            if proc:
                if proc.poll() is None:
                    bot_running = True
                else:
                    # Clean up dead process
                    del self.live_processes[login_id]
                    
            # Try to load status from file
            status_path = f"data/sessions/{login_id}_status.json"
            status_data = None
            if bot_running and os.path.exists(status_path):
                try:
                    with open(status_path, "r") as f:
                        status_data = json.load(f)
                except:
                    pass
                    
            if status_data:
                accounts_list.append({
                    "login": login_id,
                    "name": acct["name"],
                    "bot_running": True,
                    "running_symbols": acct["symbols"],
                    "active_sessions": status_data.get("active_sessions", []),
                    "account": status_data.get("account", {})
                })
            else:
                accounts_list.append({
                    "login": login_id,
                    "name": acct["name"],
                    "bot_running": bot_running,
                    "running_symbols": acct["symbols"] if bot_running else [],
                    "active_sessions": [],
                    "account": {
                        "balance": 0.0,
                        "equity": 0.0,
                        "margin_free": 0.0,
                        "profit": 0.0,
                        "login": login_id,
                        "server": "OFFLINE",
                        "currency": "USD"
                    }
                })

        # 2. Simulated Account details
        sim_acc = self.sim_manager.account_info()
        # Query simulation active positions
        token = trading_mode_var.set("forward_test")
        sim_positions = mt5.positions_get()
        sim_floating = sum(p.profit + p.swap for p in sim_positions) if sim_positions else 0.0
        sim_acc_dict = {
            "balance": round(sim_acc.balance, 2),
            "equity": round(sim_acc.balance + sim_floating, 2),
            "margin_free": round(sim_acc.balance, 2),
            "profit": round(sim_floating, 2),
            "login": 9999999,
            "server": "FORWARD_TEST_SIMULATOR",
            "currency": "USD"
        }
        trading_mode_var.reset(token)

        # Gather simulated sessions info
        sim_sessions = []
        token = trading_mode_var.set("forward_test")
        for sym in self.running_symbols["forward_test"]:
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
            
            sim_sessions.append({
                "symbol": sym,
                "layers": layers,
                "direction": direction,
                "first_entry_price": first_entry_price,
                "net_profit": round(net_profit, 2),
                "risk_level": btc_config.get_risk_level(),
                "current_price": current_price
            })
        trading_mode_var.reset(token)

        return {
            "live": {
                "accounts": accounts_list
            },
            "forward_test": {
                "bot_running": len(self.running_symbols["forward_test"]) > 0,
                "running_symbols": self.running_symbols["forward_test"],
                "active_sessions": sim_sessions,
                "account": sim_acc_dict
            },
            "mt5_connected": self.mt5_connected
        }

    def start_bot(self, login: int):
        with self.lock:
            # Stop if already running
            self.stop_bot(login)
            
            accounts = load_accounts()
            acct = next((a for a in accounts if a["login"] == login), None)
            if not acct:
                raise Exception(f"Account with login {login} not found.")
                
            cmd = [
                sys.executable,
                "live_account_runner.py",
                "--login", str(acct["login"]),
                "--password", acct["password"],
                "--server", acct["server"],
                "--path", acct["path"],
                "--symbols", ",".join(acct["symbols"])
            ]
            
            # Clean up old status/positions files to prevent stale values from loading
            for suffix in ["_status.json", "_positions.json", "_close_all.flag"]:
                p_path = f"data/sessions/{login}{suffix}"
                if os.path.exists(p_path):
                    try:
                        os.remove(p_path)
                    except:
                        pass
                        
            proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.live_processes[login] = proc
            logger.info(f"Spawned live runner process for login {login} (pid={proc.pid})")

    def stop_bot(self, login: int):
        with self.lock:
            proc = self.live_processes.get(login)
            if proc:
                logger.info(f"Stopping live runner process for login {login}...")
                proc.terminate()
                try:
                    proc.wait(timeout=3.0)
                except subprocess.TimeoutExpired:
                    proc.kill()
                del self.live_processes[login]

            # Clean up any duplicate or zombie runner processes for this account
            try:
                import subprocess as sp
                cmd_find = f'wmic process where "name=\'python.exe\' and commandline like \'%live_account_runner.py%--login {login}%\'" get processid'
                out = sp.check_output(cmd_find, shell=True).decode()
                for line in out.splitlines():
                    parts = line.strip().split()
                    if parts and parts[0].isdigit():
                        pid_to_kill = int(parts[0])
                        if pid_to_kill != os.getpid():
                            sp.run(f'taskkill /F /PID {pid_to_kill}', shell=True, stdout=sp.DEVNULL, stderr=sp.DEVNULL)
            except Exception as e:
                logger.error(f"Error cleaning zombie processes for login {login}: {e}")
                
            # Clean up status file
            status_path = f"data/sessions/{login}_status.json"
            if os.path.exists(status_path):
                try:
                    os.remove(status_path)
                except:
                    pass

    def close_all_positions(self, login: int):
        logger.info(f"Writing emergency close flag for live account login {login}...")
        flag_path = f"data/sessions/{login}_close_all.flag"
        try:
            with open(flag_path, "w") as f:
                f.write("1")
        except Exception as e:
            logger.error(f"Failed to write emergency close flag: {e}")

    def start_sim_bot(self, symbols: List[str]):
        with self.lock:
            self.stop_sim_bot()
            
            logger.info("Starting loops in Simulated FORWARD TEST mode.")
            starting_balance = self.sim_manager.balance

            def thread_wrapper(sym, start_bal, stop_ev):
                trading_mode_var.set("forward_test")
                btc_config.set_active_symbol(sym)
                logger.info(f"Context variables set for simulation thread: symbol={sym}")
                btc_layer_bot.run_trading_loop(sym, start_bal, stop_ev)

            for sym in symbols:
                mt5.symbol_select(sym, True)
                
                stop_event = threading.Event()
                self.stop_events["forward_test"][sym] = stop_event
                
                t = threading.Thread(
                    target=thread_wrapper,
                    args=(sym, starting_balance, stop_event),
                    name=f"WebBotThread-forward_test-{sym}"
                )
                t.daemon = True
                t.start()
                self.threads["forward_test"][sym] = t
                self.running_symbols["forward_test"].append(sym)
                logger.info(f"Simulated bot thread started for {sym}.")

    def stop_sim_bot(self):
        with self.lock:
            if not self.running_symbols["forward_test"]:
                return
                
            logger.info("Stopping active simulation bot loops...")
            for sym, stop_event in self.stop_events["forward_test"].items():
                stop_event.set()
                
            for sym, t in self.threads["forward_test"].items():
                t.join(timeout=2.0)
                logger.info(f"Simulation thread for {sym} stopped.")
                
            self.threads["forward_test"].clear()
            self.stop_events["forward_test"].clear()
            self.running_symbols["forward_test"].clear()
            logger.info("All active simulation loops stopped.")

    def close_all_sim_positions(self):
        import btc_trading
        logger.info("Emergency: closing all open positions for active simulation loops.")
        token = trading_mode_var.set("forward_test")
        for sym in self.running_symbols["forward_test"]:
            btc_config.set_active_symbol(sym)
            magics = [
                getattr(btc_config, 'MAGIC_NUMBER', 20260523),
                getattr(btc_config, 'MAGIC_NUMBER_M5', None),
                getattr(btc_config, 'MAGIC_NUMBER_M15', None)
            ]
            for magic in magics:
                if magic is not None:
                    btc_trading.close_all_open_positions("GUI Emergency Close", symbol=sym, magic=magic)
        trading_mode_var.reset(token)

# Instantiate the singleton BotManager after the class is defined
bot_manager = None
bot_manager = BotManager()

# --- ACCOUNTS CONFIG ---
ACCOUNTS_FILE = "config/accounts_settings.json"

def load_accounts():
    if not os.path.exists(ACCOUNTS_FILE):
        return []
    try:
        with open(ACCOUNTS_FILE, "r") as f:
            return json.load(f)
    except:
        return []

def save_accounts(accounts):
    os.makedirs("config", exist_ok=True)
    with open(ACCOUNTS_FILE, "w") as f:
        json.dump(accounts, f, indent=2)

class AccountConfig(BaseModel):
    name: str
    login: int
    password: str
    server: str
    path: str
    symbols: List[str]

# --- API MODELS ---
class StartRequest(BaseModel):
    symbols: Optional[List[str]] = None
    mode: str  # "live" | "forward_test"
    login: Optional[int] = None

class StopRequest(BaseModel):
    mode: str
    login: Optional[int] = None

class CloseAllRequest(BaseModel):
    mode: str
    login: Optional[int] = None

class ConfigUpdateRequest(BaseModel):
    symbol: str
    config: dict

# --- ENDPOINTS ---

@app.on_event("startup")
def startup_event():
    # Kill any orphaned live account runner processes on startup
    try:
        import subprocess as sp
        import os
        cmd_find = 'wmic process where "name=\'python.exe\' and commandline like \'%%live_account_runner.py%%\'" get processid'
        out = sp.check_output(cmd_find, shell=True).decode()
        for line in out.splitlines():
            parts = line.strip().split()
            if parts and parts[0].isdigit():
                pid_to_kill = int(parts[0])
                if pid_to_kill != os.getpid():
                    sp.run(f'taskkill /F /PID {pid_to_kill}', shell=True, stdout=sp.DEVNULL, stderr=sp.DEVNULL)
    except Exception as e:
        logger.error(f"Error cleaning zombie processes on startup: {e}")

    bot_manager.connect_mt5()

@app.on_event("shutdown")
def shutdown_event():
    bot_manager.stop_sim_bot()
    # Terminate all live subprocesses
    for login_id, proc in list(bot_manager.live_processes.items()):
        try:
            proc.terminate()
            proc.wait(timeout=1.0)
        except:
            pass
    try:
        mt5.shutdown()
    except:
        pass

@app.get("/api/accounts")
def get_accounts():
    return load_accounts()

@app.post("/api/accounts")
def add_update_account(req: AccountConfig):
    accounts = load_accounts()
    # Remove existing if any
    accounts = [a for a in accounts if a["login"] != req.login]
    accounts.append(req.dict())
    save_accounts(accounts)
    return {"status": "success", "message": f"Account {req.login} configured successfully"}

@app.delete("/api/accounts/{login}")
def delete_account(login: int):
    # Stop bot if running
    bot_manager.stop_bot(login)
    accounts = load_accounts()
    accounts = [a for a in accounts if a["login"] != login]
    save_accounts(accounts)
    return {"status": "success", "message": f"Account {login} deleted successfully"}

@app.get("/api/status")
def get_status():
    try:
        return bot_manager.get_status()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/positions")
def get_positions(mode: str = "forward_test", login: Optional[int] = None):
    try:
        if mode == "live" and login:
            positions_path = f"data/sessions/{login}_positions.json"
            if os.path.exists(positions_path):
                with open(positions_path, "r") as f:
                    return json.load(f)
            return []
            
        token = trading_mode_var.set(mode)
        raw_positions = mt5.positions_get()
        trading_mode_var.reset(token)
        
        if not raw_positions:
            return []
        
        serialized = []
        for p in raw_positions:
            serialized.append({
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
        return serialized
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/history")
def get_history(mode: str = "forward_test", login: Optional[int] = None):
    try:
        if mode == "live" and login:
            history_path = f"data/sessions/{login}_history.json"
            if os.path.exists(history_path):
                with open(history_path, "r") as f:
                    return json.load(f)
            return []
            
        history = []
        if mode == "forward_test":
            db_path = "data/database/forward_test_market_data.sqlite"
            if os.path.exists(db_path):
                conn = sqlite3.connect(db_path)
                try:
                    cursor = conn.cursor()
                    cursor.execute("SELECT value FROM simulated_account WHERE key = 'balance'")
                    row = cursor.fetchone()
                    current_balance = float(row[0]) if row else 10000.0
                    
                    cursor.execute("SELECT time_close, profit, swap, exit_reason, symbol, ticket FROM simulated_deals WHERE entry = 1 ORDER BY time_close ASC")
                    deals = cursor.fetchall()
                except Exception as ex:
                    logger.error(f"Error querying simulation deals: {ex}")
                    deals = []
                finally:
                    conn.close()
                
                total_profit = sum(d[1] + d[2] for d in deals)
                initial_balance = current_balance - total_profit
                
                running_balance = initial_balance
                history.append({
                    "time": datetime.fromtimestamp(int(time.time() - 30 * 86400), tz=timezone.utc).isoformat(),
                    "balance": round(initial_balance, 2),
                    "profit": 0.0,
                    "reason": "Initial",
                    "symbol": ""
                })
                
                for d in deals:
                    running_balance += d[1] + d[2]
                    dt = datetime.fromtimestamp(d[0], tz=timezone.utc)
                    history.append({
                        "time": dt.isoformat(),
                        "balance": round(running_balance, 2),
                        "profit": round(d[1], 2),
                        "reason": d[3],
                        "symbol": d[4],
                        "ticket": d[5]
                    })
        else:
            now = int(time.time())
            start_time = now - 30 * 86400
            
            bot_manager.bridge.ensure_connection()
            token = trading_mode_var.set("live")
            deals = mt5.history_deals_get(start_time, now + 10)
            trading_mode_var.reset(token)
            
            if deals:
                deals = sorted(list(deals), key=lambda x: x.time)
                closed_deals = [d for d in deals if d.entry == mt5.DEAL_ENTRY_OUT]
                
                token = trading_mode_var.set("live")
                acc_info = mt5.account_info()
                trading_mode_var.reset(token)
                
                current_balance = acc_info.balance if acc_info else 0.0
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
                    
        return history
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/config")
def get_config():
    import importlib
    configs = {}
    active_symbols = btc_config.ACTIVE_SYMBOLS
    
    settings_path = "config/gui_settings.json"
    saved_settings = {}
    if os.path.exists(settings_path):
        try:
            with open(settings_path, 'r') as f:
                saved_settings = json.load(f)
        except Exception as e:
            logger.error(f"Error loading gui_settings.json: {e}")
            
    for sym in active_symbols:
        try:
            mod = importlib.import_module(f"config.symbols.{sym}")
        except ImportError:
            try:
                mod = importlib.import_module("config.symbols.BTCUSDc")
            except:
                mod = None
                
        sym_defaults = {}
        if mod:
            sym_defaults = {
                "LOT_SIZE": getattr(mod, "LOT_SIZE", 0.01),
                "MAX_SPREAD_USD": getattr(mod, "MAX_SPREAD_USD", 15.0),
                "LAYERING_MODE": getattr(mod, "LAYERING_MODE", "USD"),
                "LAYERING_STEP_ATR_MULT": getattr(mod, "LAYERING_STEP_ATR_MULT", 1.0),
                "LAYERING_STEP_USD": getattr(mod, "LAYERING_STEP_USD", 100.0),
                "TAKE_PROFIT_PER_LAYER_USD": getattr(mod, "TAKE_PROFIT_PER_LAYER_USD", 0.20),
                "MAX_LAYERS": getattr(mod, "MAX_LAYERS", None),
                "LOW_RISK_OVERRIDES": getattr(mod, "LOW_RISK_OVERRIDES", {}),
                "MODERATE_RISK_OVERRIDES": getattr(mod, "MODERATE_RISK_OVERRIDES", {}),
            }
            
        sym_saved = saved_settings.get(sym, {})
        configs[sym] = {**sym_defaults, **sym_saved}
        
    return configs

@app.post("/api/config")
def update_config(req: ConfigUpdateRequest):
    symbol = req.symbol
    new_config = req.config
    
    if symbol not in btc_config.ACTIVE_SYMBOLS:
        raise HTTPException(status_code=400, detail=f"Invalid symbol: {symbol}")
        
    settings_path = "config/gui_settings.json"
    saved_settings = {}
    if os.path.exists(settings_path):
        try:
            with open(settings_path, 'r') as f:
                saved_settings = json.load(f)
        except:
            pass
            
    saved_settings[symbol] = new_config
    
    try:
        os.makedirs("config", exist_ok=True)
        with open(settings_path, 'w') as f:
            json.dump(saved_settings, f, indent=4)
        logger.info(f"Configuration updated for {symbol}.")
        return {"status": "success", "message": f"Configuration saved for {symbol}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/control")
def start_stop_bot(req: StartRequest):
    try:
        if req.mode == "live":
            login = req.login
            if not login:
                accounts = load_accounts()
                if accounts:
                    login = accounts[0]["login"]
                    logger.info(f"Start request missing login. Defaulting to first configured account: {login}")
            
            if not login:
                raise HTTPException(status_code=400, detail="Missing login for live mode start request")
            bot_manager.start_bot(login=login)
            return {"status": "success", "message": f"Live bot process initiated for account {login}"}
        else:
            bot_manager.start_sim_bot(symbols=req.symbols)
            return {"status": "success", "message": f"Simulation bot threads started for {', '.join(req.symbols)}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/control/stop")
def stop_bot_api(req: StopRequest):
    try:
        if req.mode == "live":
            login = req.login
            if not login:
                accounts = load_accounts()
                if accounts:
                    login = accounts[0]["login"]
                    logger.info(f"Stop request missing login. Defaulting to first configured account: {login}")
            
            if not login:
                raise HTTPException(status_code=400, detail="Missing login for live mode stop request")
            bot_manager.stop_bot(login=login)
            return {"status": "success", "message": f"Live bot process for account {login} stopped successfully."}
        else:
            bot_manager.stop_sim_bot()
            return {"status": "success", "message": "Simulation bot threads stopped successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/control/close-all")
def close_all_positions_api(req: CloseAllRequest):
    try:
        if req.mode == "live":
            login = req.login
            if not login:
                accounts = load_accounts()
                if accounts:
                    login = accounts[0]["login"]
                    logger.info(f"Close-all request missing login. Defaulting to first configured account: {login}")
            
            if not login:
                raise HTTPException(status_code=400, detail="Missing login for live mode close-all request")
            bot_manager.close_all_positions(login=login)
            return {"status": "success", "message": f"Emergency close flag set for live account {login}."}
        else:
            bot_manager.close_all_sim_positions()
            return {"status": "success", "message": "Simulation positions emergency close completed."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- BACKTEST CHANNELS ---
class BacktestRequest(BaseModel):
    symbol: str
    limit: int = 20000
    use_mt5: bool = False

def run_backtest_in_thread(symbol, limit, use_mt5):
    try:
        bot_manager.backtest_status = "running"
        bot_manager.backtest_error = None
        bot_manager.backtest_results = None
        
        from scripts.backtest_layer_bot import load_data, run_simulation
        import numpy as np
        
        logger.info(f"Starting background backtest for {symbol} (limit={limit}, use_mt5={use_mt5})")
        token = trading_mode_var.set("live")
        m1_df, m5_df, m15_df, h1_df = load_data(symbol, use_mt5=use_mt5, limit=limit)
        trading_mode_var.reset(token)
        
        if m1_df is None or m1_df.empty:
            raise Exception("Historical rates loaded empty. Run MT5 terminal or verify SQLite DB tables.")
            
        trades, equity_curve, equity_times = run_simulation(symbol, m1_df, m5_df, m15_df, h1_df)
        logger.info(f"Backtest simulation complete. Closed Trades count: {len(trades)}")
        
        if not trades:
            bot_manager.backtest_results = {
                "total_trades": 0,
                "win_rate": 0.0,
                "total_pnl": 0.0,
                "max_dd": 0.0,
                "sharpe": 0.0,
                "exit_reasons": {},
                "layer_distribution": {},
                "equity_curve": [],
                "trades": []
            }
            bot_manager.backtest_status = "completed"
            return
            
        trades_df = pd.DataFrame(trades)
        
        total_trades = len(trades_df)
        win_trades = trades_df[trades_df['pnl'] > 0]
        win_rate = (len(win_trades) / total_trades) * 100
        total_pnl = float(trades_df['pnl'].sum())
        
        equity_series = pd.Series(equity_curve)
        cum_max = equity_series.cummax()
        drawdown = (cum_max - equity_series) / cum_max * 100
        max_dd = float(drawdown.max())
        
        daily_equity = pd.DataFrame({'time': equity_times, 'equity': equity_curve})
        daily_equity['date'] = pd.to_datetime(daily_equity['time']).dt.date
        daily_res = daily_equity.groupby('date')['equity'].last()
        daily_pct = daily_res.pct_change().dropna()
        std = daily_pct.std()
        sharpe = float(daily_pct.mean() / std * np.sqrt(252)) if std > 0 else 0.0
        
        curve_data = []
        step = max(1, len(equity_curve) // 1000)
        for idx in range(0, len(equity_curve), step):
            t_val = equity_times[idx]
            t_str = t_val.isoformat() if isinstance(t_val, pd.Timestamp) else str(t_val)
            curve_data.append({
                "time": t_str,
                "equity": round(float(equity_curve[idx]), 2)
            })
            
        trades_list = []
        for _, r in trades_df.iterrows():
            trades_list.append({
                "ticket": int(r['ticket']),
                "type": r['type'],
                "entry_time": r['entry_time'].isoformat() if isinstance(r['entry_time'], pd.Timestamp) else str(r['entry_time']),
                "exit_time": r['exit_time'].isoformat() if isinstance(r['exit_time'], pd.Timestamp) else str(r['exit_time']),
                "entry_price": float(r['entry_price']),
                "exit_price": float(r['exit_price']),
                "pnl": round(float(r['pnl']), 2),
                "exit_reason": r['exit_reason'],
                "basket_layers": int(r['basket_layers']) if 'basket_layers' in r else 1
            })
            
        exit_reasons = trades_df['exit_reason'].value_counts().to_dict()
        
        baskets = trades_df.groupby('exit_time').first()
        layer_dist = {int(k): int(v) for k, v in baskets['basket_layers'].value_counts().items()}
        
        bot_manager.backtest_results = {
            "total_trades": total_trades,
            "win_rate": round(float(win_rate), 2),
            "total_pnl": round(float(total_pnl), 2),
            "max_dd": round(float(max_dd), 2),
            "sharpe": round(float(sharpe), 4),
            "exit_reasons": exit_reasons,
            "layer_distribution": layer_dist,
            "equity_curve": curve_data,
            "trades": trades_list
        }
        bot_manager.backtest_status = "completed"
        logger.info("Backtest simulation completed successfully.")
    except Exception as e:
        logger.error(f"Error in backtest thread: {e}", exc_info=True)
        bot_manager.backtest_error = str(e)
        bot_manager.backtest_status = "error"

@app.post("/api/backtest/run")
def run_backtest(req: BacktestRequest):
    if bot_manager.backtest_status == "running":
        raise HTTPException(status_code=400, detail="A backtest simulation is already running.")
        
    bot_manager.backtest_thread = threading.Thread(
        target=run_backtest_in_thread,
        args=(req.symbol, req.limit, req.use_mt5)
    )
    bot_manager.backtest_thread.daemon = True
    bot_manager.backtest_thread.start()
    return {"status": "success", "message": "Backtest initiated."}

@app.get("/api/backtest/status")
def get_backtest_status():
    return {
        "status": bot_manager.backtest_status,
        "error": bot_manager.backtest_error
    }

@app.get("/api/backtest/results")
def get_backtest_results():
    if bot_manager.backtest_status != "completed":
        raise HTTPException(status_code=400, detail="Backtest results not ready or failed.")
    return bot_manager.backtest_results

def tail_log_file(filename, n=200):
    if not os.path.exists(filename):
        return []
    try:
        with open(filename, 'rb') as f:
            f.seek(0, 2)
            file_size = f.tell()
            # Read a chunk from the end of the file (64KB is plenty for last 200 lines)
            read_size = min(file_size, 65536)
            if read_size > 0:
                f.seek(file_size - read_size)
                chunk = f.read(read_size)
                decoded = chunk.decode('utf-8', errors='ignore')
                lines = [line.strip() for line in decoded.splitlines() if line.strip()]
                return lines[-n:]
            return []
    except Exception as e:
        logger.error(f"Error in tail_log_file: {e}")
        try:
            with open(filename, 'r', encoding='utf-8', errors='ignore') as f:
                return [line.strip() for line in f.readlines()[-n:]]
        except:
            return []

@app.get("/api/logs")
def get_logs(mode: str = "forward_test", login: Optional[int] = None):
    if mode == "live" and login:
        log_path = f"data/logs/{login}.log"
    elif mode == "live":
        log_path = "btc_layer_bot_live.log"
    else:
        log_path = "btc_layer_bot_sim.log"
        
    return {"logs": tail_log_file(log_path, 200)}

# DXY Rust service proxy endpoints below
@app.get("/api/dxy/latest")
def get_dxy_latest():
    """
    Proxies request to the Rust DXY service to get the latest Dollar Index data.
    """
    import requests
    try:
        response = requests.get("http://127.0.0.1:8081/api/dxy/latest", timeout=5)
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            raise HTTPException(status_code=404, detail="No DXY records found.")
        else:
            raise HTTPException(status_code=response.status_code, detail=response.text)
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=503, detail=f"DXY service unavailable: {e}")

@app.get("/api/dxy/historical")
def get_dxy_historical(limit: Optional[int] = 1000):
    """
    Proxies request to the Rust DXY service to get historical DXY data.
    """
    import requests
    try:
        response = requests.get(f"http://127.0.0.1:8081/api/dxy/historical?limit={limit}", timeout=5)
        if response.status_code == 200:
            return response.json()
        else:
            raise HTTPException(status_code=response.status_code, detail=response.text)
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=503, detail=f"DXY service unavailable: {e}")

@app.post("/api/dxy/harvest")
def post_dxy_harvest():
    """
    Triggers an immediate harvest on the Rust DXY service.
    """
    import requests
    try:
        response = requests.post("http://127.0.0.1:8081/api/dxy/harvest", timeout=15)
        if response.status_code == 200:
            return response.json()
        else:
            raise HTTPException(status_code=response.status_code, detail=response.text)
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=503, detail=f"DXY service unavailable: {e}")

@app.get("/api/market/dxy")
def get_dxy():
    """
    Proxies to the Rust DXY service to return current price, change, and change percent.
    """
    import requests
    try:
        response = requests.get("http://127.0.0.1:8081/api/dxy/historical?limit=2", timeout=5)
        if response.status_code == 200:
            records = response.json()
            if not records:
                raise HTTPException(status_code=404, detail="No DXY records found.")
            
            latest = records[-1]
            price = latest["close"]
            change = 0.0
            change_percent = 0.0
            
            if len(records) >= 2:
                prev = records[-2]
                if prev["close"] > 0:
                    change = price - prev["close"]
                    change_percent = (change / prev["close"]) * 100
            
            return {
                "symbol": "DXY",
                "price": round(price, 3),
                "change": round(change, 3),
                "change_percent": round(change_percent, 2),
                "source": "RustDXYService"
            }
        else:
            raise HTTPException(status_code=response.status_code, detail=response.text)
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=503, detail=f"DXY service unavailable: {e}")

@app.get("/api/market/dxy/history")
def get_dxy_history(range: str = "7d"):
    """
    Proxies to the Rust DXY service and formats historical data for the frontend chart.
    """
    import requests
    limit = 168  # Default 7d (24 * 7)
    if range == "1d":
        limit = 24
    elif range == "30d":
        limit = 720
    elif range == "3y" or range == "5y":
        limit = 20000
        
    try:
        response = requests.get(f"http://127.0.0.1:8081/api/dxy/historical?limit={limit}", timeout=5)
        if response.status_code == 200:
            records = response.json()
            history_list = []
            for rec in records:
                iso_time = rec["time"].replace(" ", "T")
                history_list.append({
                    "time": iso_time,
                    "value": round(rec["close"], 3)
                })
            return history_list
        else:
            raise HTTPException(status_code=response.status_code, detail=response.text)
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=503, detail=f"DXY service unavailable: {e}")

@app.get("/api/symbols")
def get_symbols():
    symbols_list = btc_config.ACTIVE_SYMBOLS
    available = []
    if bot_manager.mt5_connected:
        try:
            mt_symbols = mt5.symbols_get()
            if mt_symbols:
                available = [s.name for s in mt_symbols if s.visible]
        except Exception as e:
            logger.error(f"Error fetching symbols: {e}")
            
    return {
        "active": symbols_list,
        "available": available if available else symbols_list
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
