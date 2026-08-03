import os
import time
import sqlite3
import logging
import threading
from datetime import datetime
import MetaTrader5 as mt5
import btc_config

logger = logging.getLogger(__name__)

# Symbol specific details for contract size mapping
SYMBOL_SPECS = {
    "BTCUSD": {"contract_size": 1.0, "pip_size": 1.0},
    "BTCUSDc": {"contract_size": 1.0, "pip_size": 1.0},
    "BTCUSDm": {"contract_size": 1.0, "pip_size": 1.0},
    "XAUUSDc": {"contract_size": 100.0, "pip_size": 0.01},
    "XAUUSDm": {"contract_size": 100.0, "pip_size": 0.01},
    "XAGUSDc": {"contract_size": 5000.0, "pip_size": 0.001},
    "ETHUSDc": {"contract_size": 1.0, "pip_size": 1.0},
}

def get_contract_size(symbol):
    try:
        info = mt5.symbol_info(symbol)
        if info is not None:
            return info.trade_contract_size
    except Exception:
        pass
    spec = SYMBOL_SPECS.get(symbol, {"contract_size": 1.0})
    return spec["contract_size"]

class SimulatedPosition:
    def __init__(self, ticket, symbol, pos_type, volume, price_open, magic, sl=0.0, tp=0.0, time_open=None):
        self.ticket = ticket
        self.symbol = symbol
        self.type = pos_type  # 0 for Buy (mt5.POSITION_TYPE_BUY), 1 for Sell (mt5.POSITION_TYPE_SELL)
        self.volume = volume
        self.price_open = price_open
        self.magic = magic
        self.sl = sl
        self.tp = tp
        self.time = time_open if time_open is not None else int(time.time())
        self.profit = 0.0
        self.swap = 0.0

    def update_profit(self, bid, ask, contract_size):
        # print('bid :', bid)
        # print('ask :', ask)
        # print('price_open :', self.price_open)
        # print('volume :', self.volume)
        # print('contract_size :', contract_size)
        if self.type == 0:  # BUY
            self.profit = (bid - self.price_open) * (self.volume * 100 * contract_size)
        else:  # SELL
            self.profit = (self.price_open - ask) * (self.volume * 100 * contract_size)

        # print('self.profit :', self.profit)

class SimulatedDeal:
    def __init__(self, ticket, symbol, deal_type, entry, volume, price, profit, swap, time_val, commission=0.0):
        self.ticket = ticket
        self.symbol = symbol
        self.type = deal_type  # 0 for BUY, 1 for SELL
        self.entry = entry  # 0 for DEAL_ENTRY_IN, 1 for DEAL_ENTRY_OUT, 2 for DEAL_ENTRY_INOUT
        self.volume = volume
        self.price = price
        self.profit = profit
        self.swap = swap
        self.time = time_val
        self.commission = commission

class SimulatedAccountInfo:
    def __init__(self, balance):
        self.balance = balance

class ForwardTestManager:
    def __init__(self, db_path="data/database/forward_test_market_data.sqlite", initial_balance=10000.0):
        self.db_path = db_path
        self.initial_balance = initial_balance
        self.lock = threading.RLock()
        
        self._ensure_db_setup()
        self.balance = self._load_balance()
        self.positions = self._load_open_positions()
        self.ticket_counter = self._get_next_ticket()
        
        logger.info(f"ForwardTestManager initialized. Balance: {self.balance:.2f} USD. Open Positions: {len(self.positions)}")

    def _ensure_db_setup(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS simulated_positions (
                    ticket INTEGER PRIMARY KEY,
                    symbol TEXT,
                    type INTEGER,
                    volume REAL,
                    price_open REAL,
                    magic INTEGER,
                    sl REAL,
                    tp REAL,
                    time INTEGER
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS simulated_deals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticket INTEGER,
                    symbol TEXT,
                    type INTEGER,
                    entry INTEGER,
                    volume REAL,
                    price_open REAL,
                    price_close REAL,
                    profit REAL,
                    swap REAL,
                    time_open INTEGER,
                    time_close INTEGER,
                    exit_reason TEXT,
                    magic INTEGER
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS simulated_account (
                    key TEXT PRIMARY KEY,
                    value REAL
                )
            """)
            conn.commit()
        except Exception as e:
            logger.error(f"Error setting up simulator database: {e}")
        finally:
            conn.close()

    def _load_balance(self):
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM simulated_account WHERE key = 'balance'")
            row = cursor.fetchone()
            if row:
                return float(row[0])
            else:
                cursor.execute("INSERT INTO simulated_account (key, value) VALUES ('balance', ?)", (self.initial_balance,))
                conn.commit()
                return self.initial_balance
        except Exception as e:
            logger.error(f"Error loading simulated balance: {e}")
            return self.initial_balance
        finally:
            conn.close()

    def _save_balance(self, balance):
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("INSERT OR REPLACE INTO simulated_account (key, value) VALUES ('balance', ?)", (balance,))
            conn.commit()
        except Exception as e:
            logger.error(f"Error saving simulated balance: {e}")
        finally:
            conn.close()

    def _get_next_ticket(self):
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT MAX(ticket) FROM simulated_positions")
            row1 = cursor.fetchone()
            cursor.execute("SELECT MAX(ticket) FROM simulated_deals")
            row2 = cursor.fetchone()
            t1 = row1[0] if row1 and row1[0] is not None else 0
            t2 = row2[0] if row2 and row2[0] is not None else 0
            return max(t1, t2, 100000) + 1  # start tickets at 100000 to look distinct
        except Exception as e:
            logger.error(f"Error getting next ticket: {e}")
            return 100001
        finally:
            conn.close()

    def _load_open_positions(self):
        positions = []
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT ticket, symbol, type, volume, price_open, magic, sl, tp, time FROM simulated_positions")
            rows = cursor.fetchall()
            for r in rows:
                p = SimulatedPosition(
                    ticket=r[0],
                    symbol=r[1],
                    pos_type=r[2],
                    volume=r[3],
                    price_open=r[4],
                    magic=r[5],
                    sl=r[6],
                    tp=r[7],
                    time_open=r[8]
                )
                positions.append(p)
        except Exception as e:
            logger.error(f"Error loading open positions from DB: {e}")
        finally:
            conn.close()
        return positions

    def _save_position_to_db(self, p):
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO simulated_positions (ticket, symbol, type, volume, price_open, magic, sl, tp, time)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (p.ticket, p.symbol, p.type, p.volume, p.price_open, p.magic, p.sl, p.tp, p.time))
            conn.commit()
        except Exception as e:
            logger.error(f"Error saving simulated position to DB: {e}")
        finally:
            conn.close()

    def _delete_position_from_db(self, ticket):
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM simulated_positions WHERE ticket = ?", (ticket,))
            conn.commit()
        except Exception as e:
            logger.error(f"Error deleting simulated position from DB: {e}")
        finally:
            conn.close()

    def _save_deal_to_db(self, ticket, symbol, deal_type, entry, volume, price, profit, swap, time_val, exit_reason, magic):
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO simulated_deals (ticket, symbol, type, entry, volume, price_open, price_close, profit, swap, time_open, time_close, exit_reason, magic)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (ticket, symbol, deal_type, entry, volume, price, price, profit, swap, time_val, time_val, exit_reason, magic))
            conn.commit()
        except Exception as e:
            logger.error(f"Error saving simulated deal to DB: {e}")
        finally:
            conn.close()

    # --- MT5 Mock Methods ---

    def positions_get(self, symbol=None, ticket=None):
        with self.lock:
            # First, update profits of active positions
            for p in self.positions:
                try:
                    tick = mt5.symbol_info_tick(p.symbol)
                    if tick:
                        contract_size = get_contract_size(p.symbol)
                        p.update_profit(tick.bid, tick.ask, contract_size)
                except Exception as ex:
                    logger.error(f"Error updating profit for {p.symbol}: {ex}")

            if ticket is not None:
                return [p for p in self.positions if p.ticket == ticket]
            if symbol is not None:
                return [p for p in self.positions if p.symbol == symbol]
            return list(self.positions)

    def history_deals_get(self, start_time, end_time=None):
        # Convert start_time and end_time to unix timestamps if they are datetime objects
        start_ts = start_time
        if isinstance(start_time, datetime):
            start_ts = int(start_time.timestamp())
        
        end_ts = end_time
        if end_time is None:
            end_ts = int(time.time()) + 100
        elif isinstance(end_time, datetime):
            end_ts = int(end_time.timestamp())
            
        deals = []
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT ticket, symbol, type, entry, volume, price_close, profit, swap, time_close, magic
                FROM simulated_deals
                WHERE time_close >= ? AND time_close <= ?
            """, (start_ts, end_ts))
            rows = cursor.fetchall()
            for r in rows:
                d = SimulatedDeal(
                    ticket=r[0],
                    symbol=r[1],
                    deal_type=r[2],
                    entry=r[3],
                    volume=r[4],
                    price=r[5],
                    profit=r[6],
                    swap=r[7],
                    time_val=r[8]
                )
                deals.append(d)
        except Exception as e:
            logger.error(f"Error loading simulated deals from DB: {e}")
        finally:
            conn.close()
        return deals

    def account_info(self):
        return SimulatedAccountInfo(self.balance)

    # --- btc_trading Mock Methods ---

    def open_trade(self, direction, entry_price, sl_price, tp_price, symbol=None, magic=None):
        target_symbol = symbol if symbol is not None else btc_config.SYMBOL
        
        # Determine lot size dynamically
        lot_size = btc_config.LOT_SIZE
        magic_number = magic
        if magic_number is None:
            magic_number = btc_config.MAGIC_NUMBER
            if target_symbol != btc_config.SYMBOL:
                try:
                    import importlib
                    sym_mod = importlib.import_module(f"config.symbols.{target_symbol}")
                    magic_number = getattr(sym_mod, "MAGIC_NUMBER", magic_number)
                except Exception:
                    pass

        with self.lock:
            ticket = self.ticket_counter
            self.ticket_counter += 1
            
            p = SimulatedPosition(
                ticket=ticket,
                symbol=target_symbol,
                pos_type=0 if direction == "BUY" else 1,
                volume=float(lot_size),
                price_open=float(entry_price),
                magic=magic_number,
                sl=float(sl_price),
                tp=float(tp_price),
                time_open=int(time.time())
            )
            self.positions.append(p)
            self._save_position_to_db(p)
            
            # Log opening deal (profit=0, exit_reason="")
            self._save_deal_to_db(
                ticket=ticket,
                symbol=target_symbol,
                deal_type=0 if direction == "BUY" else 1,
                entry=0, # mt5.DEAL_ENTRY_IN = 0
                volume=float(lot_size),
                price=float(entry_price),
                profit=0.0,
                swap=0.0,
                time_val=p.time,
                exit_reason="",
                magic=magic_number
            )
            
            logger.info(f"[SIMULATED] Opened {direction} ({ticket}) at {entry_price:.2f} (volume: {lot_size})")
            
            # Log to TradeRsiLogger (using simulation DB) in a background thread to prevent blocking
            try:
                from data.trade_logger import TradeRsiLogger
                db_logger = TradeRsiLogger(db_path=self.db_path)
                tick = mt5.symbol_info_tick(target_symbol)
                spread_val = tick.ask - tick.bid if tick is not None else None
                threading.Thread(
                    target=db_logger.log_trade,
                    args=(ticket, direction, target_symbol, entry_price, lot_size),
                    kwargs={"spread": spread_val},
                    daemon=True
                ).start()
            except Exception as ex:
                logger.error(f"Error logging simulated trade to DB: {ex}")
                
            return ticket

    def close_all_open_positions(self, reason="Shutdown", symbol=None, magic=None):
        target_symbol = symbol if symbol is not None else btc_config.SYMBOL
        target_magic = magic
        if target_magic is None:
            target_magic = btc_config.MAGIC_NUMBER
            if target_symbol != btc_config.SYMBOL:
                try:
                    import importlib
                    sym_mod = importlib.import_module(f"config.symbols.{target_symbol}")
                    target_magic = getattr(sym_mod, "MAGIC_NUMBER", target_magic)
                except Exception:
                    pass

        with self.lock:
            # Find matching active positions to close
            matching = [p for p in self.positions if p.symbol == target_symbol and p.magic == target_magic]
            for p in matching:
                self._close_position_locked(p, reason)

    def _close_position_locked(self, position, reason):
        if position in self.positions:
            self.positions.remove(position)
            
        tick = mt5.symbol_info_tick(position.symbol)
        if tick is None:
            logger.error(f"Failed to get tick for closing position {position.ticket}")
            close_price = position.price_open
        else:
            close_price = tick.bid if position.type == 0 else tick.ask
            
        # Calculate final profit
        contract_size = get_contract_size(position.symbol)
        if position.type == 0:  # BUY
            profit = (close_price - position.price_open) * (position.volume * 100 * contract_size)
        else:  # SELL
            profit = (position.price_open - close_price) * (position.volume * 100 * contract_size)
            
        # Apply spread deduction if configured
        spread_deduction = btc_config.SPREAD_DEDUCTION_USD * position.volume * contract_size
        net_profit = profit - spread_deduction
        
        self.balance += net_profit
        self._save_balance(self.balance)
        self._delete_position_from_db(position.ticket)
        
        # Save closing deal to DB
        close_time = int(time.time())
        self._save_deal_to_db(
            ticket=position.ticket,
            symbol=position.symbol,
            deal_type=1 if position.type == 0 else 0,
            entry=1, # mt5.DEAL_ENTRY_OUT = 1
            volume=position.volume,
            price=close_price,
            profit=net_profit,
            swap=position.swap,
            time_val=close_time,
            exit_reason=reason,
            magic=position.magic
        )
        
        logger.info(f"[SIMULATED] Closed {position.ticket} ({reason}). Net Profit: {net_profit:.2f} USD")
        
        # Log to TradeRsiLogger (using simulation DB) in a background thread to prevent blocking
        try:
            from data.trade_logger import TradeRsiLogger
            db_logger = TradeRsiLogger(db_path=self.db_path)
            spread_val = tick.ask - tick.bid if tick is not None else None
            threading.Thread(
                target=db_logger.log_trade,
                args=(position.ticket, "CLOSED", position.symbol, close_price, position.volume),
                kwargs={"profit": net_profit, "spread": spread_val},
                daemon=True
            ).start()
        except Exception as ex:
            logger.error(f"Error logging simulated close to DB: {ex}")

def patch_all(manager):
    """Monkeypatches MT5 and btc_trading functions with simulated implementations."""
    # Patch MetaTrader5 package functions
    mt5.positions_get = manager.positions_get
    mt5.history_deals_get = manager.history_deals_get
    mt5.account_info = manager.account_info
    
    # Patch btc_trading module functions
    import btc_trading
    btc_trading.open_trade = manager.open_trade
    btc_trading.close_all_open_positions = manager.close_all_open_positions
    
    # Patch __main__ and btc_layer_bot namespaces
    import sys
    for mod_name in ['__main__', 'btc_layer_bot']:
        mod = sys.modules.get(mod_name)
        if mod:
            if hasattr(mod, 'open_trade'):
                mod.open_trade = manager.open_trade
            if hasattr(mod, 'close_all_open_positions'):
                mod.close_all_open_positions = manager.close_all_open_positions
