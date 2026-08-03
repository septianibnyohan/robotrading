import os
import sys
import json
import time
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
        self.running_symbols = {"live": [], "forward_test": []}
        self.stop_events = {"live": {}, "forward_test": {}}
        self.threads = {"live": {}, "forward_test": {}}
        
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
                logger.info("MT5 connection established successfully.")
                return True
            else:
                self.mt5_connected = False
                logger.warning("MT5 connection failed.")
                return False

    def get_status(self):
        if self.mt5_connected:
            self.bridge.ensure_connection()
            
        # 1. Live Account details
        live_acc_dict = {}
        # Temporarily force 'live' context to query real MT5 balance safely
        token = trading_mode_var.set("live")
        acc_info = mt5.account_info()
        if acc_info and self.mt5_connected:
            live_acc_dict = {
                "balance": round(acc_info.balance, 2),
                "equity": round(acc_info.equity, 2),
                "margin_free": round(acc_info.margin_free, 2),
                "profit": round(acc_info.profit, 2),
                "login": acc_info.login,
                "server": acc_info.server,
                "currency": acc_info.currency
            }
        else:
            live_acc_dict = {
                "balance": 0.0,
                "equity": 0.0,
                "margin_free": 0.0,
                "profit": 0.0,
                "login": 0,
                "server": "OFFLINE",
                "currency": "USD"
            }
        trading_mode_var.reset(token)

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

        # Gather sessions info per mode
        sessions = {"live": [], "forward_test": []}
        for mode in ["live", "forward_test"]:
            token = trading_mode_var.set(mode)
            for sym in self.running_symbols[mode]:
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
                
                sessions[mode].append({
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
                "bot_running": len(self.running_symbols["live"]) > 0,
                "running_symbols": self.running_symbols["live"],
                "active_sessions": sessions["live"],
                "account": live_acc_dict
            },
            "forward_test": {
                "bot_running": len(self.running_symbols["forward_test"]) > 0,
                "running_symbols": self.running_symbols["forward_test"],
                "active_sessions": sessions["forward_test"],
                "account": sim_acc_dict
            },
            "mt5_connected": self.mt5_connected
        }

    def start_bot(self, symbols: List[str], mode: str = "forward_test"):
        with self.lock:
            # Stop existing bot threads for this mode
            self._stop_bot_unlocked(mode)
            
            # Ensure connection
            self.connect_mt5()
            
            if mode == "live":
                logger.info("Starting loops in LIVE TRADING mode.")
                acc_info = mt5.account_info()
                if not acc_info:
                    raise Exception("Failed to start bot in live mode: MT5 terminal is not connected.")
                from btc_risk import get_daily_realized_profit
                today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
                starting_balance = acc_info.balance - get_daily_realized_profit(today)
            else:
                logger.info("Starting loops in Simulated FORWARD TEST mode.")
                starting_balance = self.sim_manager.balance

            # Target thread wrapper that sets ContextVar local values inside loop thread
            def thread_wrapper(sym, start_bal, stop_ev, m):
                trading_mode_var.set(m)
                btc_config.set_active_symbol(sym)
                logger.info(f"Context variables set for thread: symbol={sym}, mode={m}")
                btc_layer_bot.run_trading_loop(sym, start_bal, stop_ev)

            for sym in symbols:
                mt5.symbol_select(sym, True)
                
                stop_event = threading.Event()
                self.stop_events[mode][sym] = stop_event
                
                t = threading.Thread(
                    target=thread_wrapper,
                    args=(sym, starting_balance, stop_event, mode),
                    name=f"WebBotThread-{mode}-{sym}"
                )
                t.daemon = True
                t.start()
                self.threads[mode][sym] = t
                self.running_symbols[mode].append(sym)
                logger.info(f"Bot thread started for {sym} ({mode}).")

    def stop_bot(self, mode: str = "forward_test"):
        with self.lock:
            self._stop_bot_unlocked(mode)

    def _stop_bot_unlocked(self, mode: str = "forward_test"):
        if mode not in self.running_symbols or not self.running_symbols[mode]:
            return
            
        logger.info(f"Stopping active bot loops for {mode}...")
        for sym, stop_event in self.stop_events[mode].items():
            stop_event.set()
            
        for sym, t in self.threads[mode].items():
            t.join(timeout=2.0)
            logger.info(f"Thread for {sym} ({mode}) stopped.")
            
        self.threads[mode].clear()
        self.stop_events[mode].clear()
        self.running_symbols[mode].clear()
        logger.info(f"All active loops stopped for {mode}.")

    def close_all_positions(self, mode: str = "forward_test"):
        import btc_trading
        logger.info(f"Emergency: closing all open positions for active {mode} loops.")
        token = trading_mode_var.set(mode)
        for sym in self.running_symbols[mode]:
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

# --- API MODELS ---
class StartRequest(BaseModel):
    symbols: List[str]
    mode: str  # "live" | "forward_test"

class StopRequest(BaseModel):
    mode: str

class CloseAllRequest(BaseModel):
    mode: str

class ConfigUpdateRequest(BaseModel):
    symbol: str
    config: dict

# --- ENDPOINTS ---

@app.on_event("startup")
def startup_event():
    bot_manager.connect_mt5()

@app.on_event("shutdown")
def shutdown_event():
    bot_manager.stop_bot("live")
    bot_manager.stop_bot("forward_test")
    try:
        mt5.shutdown()
    except:
        pass

@app.get("/api/status")
def get_status():
    try:
        return bot_manager.get_status()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/positions")
def get_positions(mode: str = "forward_test"):
    try:
        # Route to correct MT5 list
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
def get_history(mode: str = "forward_test"):
    try:
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
            # Ensure live MT5 query
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
        bot_manager.start_bot(symbols=req.symbols, mode=req.mode)
        return {"status": "success", "message": f"Bot started in {req.mode} mode for {', '.join(req.symbols)}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/control/stop")
def stop_bot_api(req: StopRequest):
    try:
        bot_manager.stop_bot(mode=req.mode)
        return {"status": "success", "message": f"Bot threads for {req.mode} stopped successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/control/close-all")
def close_all_positions_api(req: CloseAllRequest):
    try:
        bot_manager.close_all_positions(mode=req.mode)
        return {"status": "success", "message": f"Close all positions request sent for {req.mode}."}
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
        # Ensure 'live' terminal data loading for backtesting
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

@app.get("/api/logs")
def get_logs(mode: str = "forward_test"):
    log_path = "btc_layer_bot_live.log" if mode == "live" else "btc_layer_bot_sim.log"
    if not os.path.exists(log_path):
        return {"logs": []}
    try:
        with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        return {"logs": [line.strip() for line in lines[-200:]]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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
