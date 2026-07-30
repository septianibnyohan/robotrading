import os
import sys
import json
import time
import logging
import threading
import sqlite3
from datetime import datetime, timezone
import MetaTrader5 as mt5
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import btc_config
from core.mt5_bridge import MT5Bridge
from config.credentials import get_mt5_credentials
import btc_layer_bot
from core.simulator import ForwardTestManager, patch_all

# Configure Logging for Web Server
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] (WebAPI) %(message)s",
    handlers=[logging.FileHandler("btc_layer_bot.log"), logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("web_server")

app = FastAPI(title="RoboBTC SaaS API", version="1.0.0")

# Enable CORS for frontend React server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For local setup, allow all; can restrict to http://localhost:5173 if needed
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class BotManager:
    def __init__(self):
        self.bridge = MT5Bridge()
        self.stop_events = {}
        self.threads = {}
        self.running_symbols = []
        self.mode = "forward_test"  # "live" or "forward_test"
        self.sim_manager = None
        self.mt5_connected = False
        self.lock = threading.Lock()
        
        # Backtest state
        self.backtest_thread = None
        self.backtest_status = "idle"  # "idle" | "running" | "completed" | "error"
        self.backtest_results = None
        self.backtest_error = None
        
        # Save original references to unpatch when switching to live mode
        self.original_mt5_funcs = {
            "positions_get": mt5.positions_get,
            "history_deals_get": mt5.history_deals_get,
            "account_info": mt5.account_info,
        }
        import btc_trading
        self.original_btc_trading_funcs = {
            "open_trade": btc_trading.open_trade,
            "close_all_open_positions": btc_trading.close_all_open_positions,
        }

    def connect_mt5(self):
        with self.lock:
            # First initialize the bridge
            if self.bridge.connect():
                self.mt5_connected = True
                logger.info("MT5 connection established successfully.")
                return True
            else:
                self.mt5_connected = False
                logger.warning("MT5 connection failed.")
                return False

    def get_status(self):
        # Watchdog check
        if self.mt5_connected:
            self.bridge.ensure_connection()
            
        acc_dict = {}
        if self.mode == "forward_test":
            if self.sim_manager:
                sim_acc = self.sim_manager.account_info()
                floating = 0.0
                positions = self.sim_manager.positions_get()
                if positions:
                    floating = sum(p.profit + p.swap for p in positions)
                acc_dict = {
                    "balance": round(sim_acc.balance, 2),
                    "equity": round(sim_acc.balance + floating, 2),
                    "margin_free": round(sim_acc.balance, 2),
                    "profit": round(floating, 2),
                    "login": 9999999,
                    "server": "FORWARD_TEST_SIMULATOR",
                    "currency": "USD"
                }
            else:
                acc_dict = {
                    "balance": 10000.0,
                    "equity": 10000.0,
                    "margin_free": 10000.0,
                    "profit": 0.0,
                    "login": 9999999,
                    "server": "FORWARD_TEST_SIMULATOR (IDLE)",
                    "currency": "USD"
                }
        else:
            acc_info = mt5.account_info()
            if acc_info:
                acc_dict = {
                    "balance": round(acc_info.balance, 2),
                    "equity": round(acc_info.equity, 2),
                    "margin_free": round(acc_info.margin_free, 2),
                    "profit": round(acc_info.profit, 2),
                    "login": acc_info.login,
                    "server": acc_info.server,
                    "currency": acc_info.currency
                }
            else:
                acc_dict = {
                    "balance": 0.0,
                    "equity": 0.0,
                    "margin_free": 0.0,
                    "profit": 0.0,
                    "login": 0,
                    "server": "OFFLINE",
                    "currency": "USD"
                }

        active_sessions = []
        for sym in self.running_symbols:
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
            
            active_sessions.append({
                "symbol": sym,
                "layers": layers,
                "direction": direction,
                "first_entry_price": first_entry_price,
                "net_profit": round(net_profit, 2),
                "risk_level": btc_config.get_risk_level(),
                "current_price": current_price
            })

        return {
            "bot_running": len(self.running_symbols) > 0,
            "mode": self.mode,
            "mt5_connected": self.mt5_connected,
            "account": acc_dict,
            "running_symbols": self.running_symbols,
            "active_sessions": active_sessions
        }

    def start_bot(self, symbols: List[str], mode: str = "forward_test"):
        with self.lock:
            # Stop existing run if active
            self._stop_bot_unlocked()
            
            self.mode = mode
            # Ensure MT5 is connected (even simulated runs need it for real-time rates)
            self.connect_mt5()
            
            if mode == "forward_test":
                logger.info("Initializing bot in simulated FORWARD TEST mode.")
                self.sim_manager = ForwardTestManager()
                patch_all(self.sim_manager)
                starting_balance = self.sim_manager.balance
            else:
                logger.info("Initializing bot in LIVE TRADING mode.")
                self.restore_functions()
                acc_info = mt5.account_info()
                if not acc_info:
                    raise Exception("Failed to start bot in live mode: MT5 terminal is not connected.")
                from btc_risk import get_daily_realized_profit
                today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
                starting_balance = acc_info.balance - get_daily_realized_profit(today)

            for sym in symbols:
                # Select the symbol in MT5
                mt5.symbol_select(sym, True)
                
                stop_event = threading.Event()
                self.stop_events[sym] = stop_event
                
                # Start loop inside a background thread
                t = threading.Thread(
                    target=btc_layer_bot.run_trading_loop,
                    args=(sym, starting_balance, stop_event),
                    name=f"WebBotThread-{sym}"
                )
                t.daemon = True
                t.start()
                self.threads[sym] = t
                self.running_symbols.append(sym)
                logger.info(f"Bot thread started for {sym}.")

    def stop_bot(self):
        with self.lock:
            self._stop_bot_unlocked()

    def _stop_bot_unlocked(self):
        if not self.running_symbols:
            return
            
        logger.info("Stopping all active bot loops...")
        for sym, stop_event in self.stop_events.items():
            stop_event.set()
            
        for sym, t in self.threads.items():
            t.join(timeout=2.0)
            logger.info(f"Thread for {sym} stopped.")
            
        self.threads.clear()
        self.stop_events.clear()
        self.running_symbols.clear()
        logger.info("All bot threads stopped.")

    def restore_functions(self):
        # Revert mock patching
        mt5.positions_get = self.original_mt5_funcs["positions_get"]
        mt5.history_deals_get = self.original_mt5_funcs["history_deals_get"]
        mt5.account_info = self.original_mt5_funcs["account_info"]
        
        import btc_trading
        btc_trading.open_trade = self.original_btc_trading_funcs["open_trade"]
        btc_trading.close_all_open_positions = self.original_btc_trading_funcs["close_all_open_positions"]
        
        import sys
        for mod_name in ['__main__', 'btc_layer_bot']:
            mod = sys.modules.get(mod_name)
            if mod:
                if hasattr(mod, 'open_trade'):
                    mod.open_trade = self.original_btc_trading_funcs["open_trade"]
                if hasattr(mod, 'close_all_open_positions'):
                    mod.close_all_open_positions = self.original_btc_trading_funcs["close_all_open_positions"]
        logger.info("Original MT5 and trading functions restored.")

    def close_all_positions(self):
        import btc_trading
        logger.info("Requesting immediate closure of all positions for active symbols.")
        for sym in self.running_symbols:
            # Load config magic number
            btc_config.set_active_symbol(sym)
            magic = getattr(btc_config, 'MAGIC_NUMBER', 20260523)
            btc_trading.close_all_open_positions("GUI Emergency Close", symbol=sym, magic=magic)

bot_manager = BotManager()

@app.on_event("startup")
def startup_event():
    # Attempt to initialize MT5 on startup
    bot_manager.connect_mt5()

@app.on_event("shutdown")
def shutdown_event():
    bot_manager.stop_bot()
    try:
        mt5.shutdown()
    except:
        pass

# --- API MODELS ---
class StartRequest(BaseModel):
    symbols: List[str]
    mode: str  # "live" | "forward_test"

class ConfigUpdateRequest(BaseModel):
    symbol: str
    config: dict

# --- ENDPOINTS ---

@app.get("/api/status")
def get_status():
    try:
        return bot_manager.get_status()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/positions")
def get_positions():
    try:
        raw_positions = mt5.positions_get()
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
def get_history():
    try:
        history = []
        if bot_manager.mode == "forward_test":
            # Read simulated deals
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
                # Add initial point
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
            # Query MT5 deals (past 30 days)
            now = int(time.time())
            start_time = now - 30 * 86400
            
            # Watchdog check
            bot_manager.bridge.ensure_connection()
            deals = mt5.history_deals_get(start_time, now + 10)
            
            if deals:
                # Sort deals
                deals = sorted(list(deals), key=lambda x: x.time)
                # Filter closing out deals
                closed_deals = [d for d in deals if d.entry == mt5.DEAL_ENTRY_OUT]
                
                acc_info = mt5.account_info()
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
def stop_bot_api():
    try:
        bot_manager.stop_bot()
        return {"status": "success", "message": "Bot threads stopped successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/control/close-all")
def close_all_positions_api():
    try:
        bot_manager.close_all_positions()
        return {"status": "success", "message": "Close all positions request sent."}
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
        
        # Dynamically import backtest run methods
        from scripts.backtest_layer_bot import load_data, run_simulation
        import numpy as np
        
        logger.info(f"Starting background backtest for {symbol} (limit={limit}, use_mt5={use_mt5})")
        m1_df, m5_df, h1_df = load_data(symbol, use_mt5=use_mt5, limit=limit)
        
        if m1_df is None or m1_df.empty:
            raise Exception("Historical rates loaded empty. Run MT5 terminal or verify SQLite DB tables.")
            
        trades, equity_curve, equity_times = run_simulation(symbol, m1_df, m5_df, h1_df)
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
        
        # Max Drawdown
        equity_series = pd.Series(equity_curve)
        cum_max = equity_series.cummax()
        drawdown = (cum_max - equity_series) / cum_max * 100
        max_dd = float(drawdown.max())
        
        # Sharpe
        daily_equity = pd.DataFrame({'time': equity_times, 'equity': equity_curve})
        daily_equity['date'] = pd.to_datetime(daily_equity['time']).dt.date
        daily_res = daily_equity.groupby('date')['equity'].last()
        daily_pct = daily_res.pct_change().dropna()
        std = daily_pct.std()
        sharpe = float(daily_pct.mean() / std * np.sqrt(252)) if std > 0 else 0.0
        
        # Downsample curve points (max 1000) for charts
        curve_data = []
        step = max(1, len(equity_curve) // 1000)
        for idx in range(0, len(equity_curve), step):
            t_val = equity_times[idx]
            t_str = t_val.isoformat() if isinstance(t_val, pd.Timestamp) else str(t_val)
            curve_data.append({
                "time": t_str,
                "equity": round(float(equity_curve[idx]), 2)
            })
            
        # Serialize trades
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
        
        # Layer distribution
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
def get_logs():
    log_path = "btc_layer_bot.log"
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
    # Return active trading symbols and all available symbols from MT5 terminal info
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
    # Expose API on port 8000
    uvicorn.run(app, host="127.0.0.1", port=8000)
