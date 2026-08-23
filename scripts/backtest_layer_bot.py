import sys
import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime, timezone, timedelta
import logging
import argparse

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import btc_config
from btc_indicators import calculate_h1_layer_indicators, calculate_m1_layer_indicators
from data.storage import DataStorage
from monitoring.logger import setup_logging

logger = setup_logging()

# Symbol specific details
SYMBOL_SPECS = {
    "BTCUSD": {"contract_size": 1.0, "pip_size": 1.0},
    "BTCUSDc": {"contract_size": 1.0, "pip_size": 1.0},
    "BTCUSDm": {"contract_size": 1.0, "pip_size": 1.0},
    "XAUUSDc": {"contract_size": 100.0, "pip_size": 0.01},
    "XAUUSDm": {"contract_size": 100.0, "pip_size": 0.01},
    "XAGUSDc": {"contract_size": 5000.0, "pip_size": 0.001},
    "ETHUSDc": {"contract_size": 1.0, "pip_size": 1.0},
    "EURUSDc": {"contract_size": 1000.0, "pip_size": 0.0001},
    "EURJPYc": {"contract_size": 6.25, "pip_size": 0.01},
    "ETHUSDm": {"contract_size": 1.0, "pip_size": 1.0},
    "EURUSDm": {"contract_size": 1000.0, "pip_size": 0.0001},
    "EURJPYm": {"contract_size": 6.25, "pip_size": 0.01},
    "USDJPYm": {"contract_size": 6.25, "pip_size": 0.01},
}

def load_data(symbol, use_mt5=False, limit=50000, path=None, login=None, password=None, server=None):
    """Loads historical data for backtesting."""
    m1_df, m5_df, m15_df = pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    
    if symbol == "ETHUSDm" and use_mt5:
        import MetaTrader5 as mt5
        logger.info("Connecting to MT5 to fetch ETHUSDm long history using M30 base...")
        init_kwargs = {}
        if path is not None:
            init_kwargs["path"] = path
        if login is not None:
            init_kwargs["login"] = int(login)
        if password is not None:
            init_kwargs["password"] = password
        if server is not None:
            init_kwargs["server"] = server
            
        if mt5.initialize(**init_kwargs):
            btc_config.set_active_symbol(symbol)
            mt5.symbol_select(symbol, True)
            
            chunk_size = 50000
            total_downloaded = 0
            start_pos = 0
            m30_dfs = []
            from btc_indicators import rates_to_df
            
            m30_limit = 200000
            while total_downloaded < m30_limit:
                req_size = min(chunk_size, m30_limit - total_downloaded)
                rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M30, start_pos, req_size)
                if rates is None or len(rates) == 0:
                    break
                m30_dfs.append(rates_to_df(rates))
                downloaded = len(rates)
                total_downloaded += downloaded
                start_pos += downloaded
                if downloaded < req_size:
                    logger.info("Broker reached the end of M30 history.")
                    break
            
            if m30_dfs:
                m30_df = pd.concat(m30_dfs, ignore_index=True)
                m30_df = m30_df.drop_duplicates(subset=['time']).sort_values('time').reset_index(drop=True)
                m30_df['time'] = pd.to_datetime(m30_df['time'], format='mixed', utc=True).dt.tz_localize(None)
                logger.info(f"Loaded {len(m30_df)} M30 bars from MT5.")
                
                m5_df = m30_df.copy()
                m15_df = m30_df.copy()
                h1_df = m30_df.set_index('time').resample('1h').agg({
                    'open': 'first',
                    'high': 'max',
                    'low': 'min',
                    'close': 'last',
                    'tick_volume': 'sum'
                }).dropna().reset_index()
                
                m1_df = m30_df.copy()
                mt5.shutdown()
                return m1_df, m5_df, m15_df, h1_df
            mt5.shutdown()
    
    if use_mt5:
        import MetaTrader5 as mt5
        logger.info("Connecting to MT5 to fetch fresh data...")
        init_kwargs = {}
        if path is not None:
            init_kwargs["path"] = path
        if login is not None:
            init_kwargs["login"] = int(login)
        if password is not None:
            init_kwargs["password"] = password
        if server is not None:
            init_kwargs["server"] = server
            
        if mt5.initialize(**init_kwargs):
            # Set active symbol in config
            btc_config.set_active_symbol(symbol)
            mt5.symbol_select(symbol, True)
            
            # Retrieve M1 rates in chunks to bypass limits
            logger.info(f"Downloading {limit} M1 bars from MT5 in chunks...")
            chunk_size = 50000
            total_downloaded = 0
            start_pos = 0
            m1_dfs = []
            from btc_indicators import rates_to_df
            
            while total_downloaded < limit:
                req_size = min(chunk_size, limit - total_downloaded)
                rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M1, start_pos, req_size)
                if rates is None or len(rates) == 0:
                    logger.warning(f"No more M1 rates returned from MT5 at start_pos {start_pos}. Ending download.")
                    break
                m1_dfs.append(rates_to_df(rates))
                downloaded = len(rates)
                total_downloaded += downloaded
                start_pos += downloaded
                if downloaded < req_size:
                    logger.info("Broker reached the end of M1 history.")
                    break
            
            if m1_dfs:
                m1_df = pd.concat(m1_dfs, ignore_index=True)
                m1_df = m1_df.drop_duplicates(subset=['time']).sort_values('time').reset_index(drop=True)
                logger.info(f"Loaded {len(m1_df)} M1 bars from MT5.")
            else:
                logger.error("Failed to load any M1 rates from MT5.")
                
            # Retrieve M5 rates in chunks
            logger.info("Downloading M5 bars from MT5 in chunks...")
            m5_limit = limit // 5
            total_m5_downloaded = 0
            start_pos_m5 = 0
            m5_dfs = []
            while total_m5_downloaded < m5_limit:
                req_size = min(chunk_size, m5_limit - total_m5_downloaded)
                rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, start_pos_m5, req_size)
                if rates is None or len(rates) == 0:
                    break
                m5_dfs.append(rates_to_df(rates))
                downloaded = len(rates)
                total_m5_downloaded += downloaded
                start_pos_m5 += downloaded
                if downloaded < req_size:
                    logger.info("Broker reached the end of M5 history.")
                    break
            if m5_dfs:
                m5_df = pd.concat(m5_dfs, ignore_index=True)
                m5_df = m5_df.drop_duplicates(subset=['time']).sort_values('time').reset_index(drop=True)
                logger.info(f"Loaded {len(m5_df)} M5 bars from MT5.")
            else:
                logger.warning("Failed to fetch M5 rates. Will resample from M1.")
                
            # Retrieve M15 rates in chunks
            logger.info("Downloading M15 bars from MT5 in chunks...")
            m15_limit = limit // 15
            total_m15_downloaded = 0
            start_pos_m15 = 0
            m15_dfs = []
            while total_m15_downloaded < m15_limit:
                req_size = min(chunk_size, m15_limit - total_m15_downloaded)
                rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, start_pos_m15, req_size)
                if rates is None or len(rates) == 0:
                    break
                m15_dfs.append(rates_to_df(rates))
                downloaded = len(rates)
                total_m15_downloaded += downloaded
                start_pos_m15 += downloaded
                if downloaded < req_size:
                    logger.info("Broker reached the end of M15 history.")
                    break
            if m15_dfs:
                m15_df = pd.concat(m15_dfs, ignore_index=True)
                m15_df = m15_df.drop_duplicates(subset=['time']).sort_values('time').reset_index(drop=True)
                logger.info(f"Loaded {len(m15_df)} M15 bars from MT5.")
            else:
                logger.warning("Failed to fetch M15 rates. Will resample from M1.")
            
            mt5.shutdown()
        else:
            logger.warning(f"Could not connect to MT5: {mt5.last_error()}. Falling back to SQLite.")
            
    if m1_df.empty or m5_df.empty or m15_df.empty:
        storage = DataStorage()
        logger.info(f"Loading data from local SQLite database for {symbol}...")
        m1_df = storage.load_rates(symbol, 1, limit=limit)
        try:
            m5_df = storage.load_rates(symbol, 5, limit=limit)
        except Exception:
            logger.info(f"No M5 table found for {symbol}, will resample from M1.")
            m5_df = pd.DataFrame()
        try:
            m15_df = storage.load_rates(symbol, 15, limit=limit)
        except Exception:
            logger.info(f"No M15 table found for {symbol}, will resample from M1.")
            m15_df = pd.DataFrame()
            
    if m1_df.empty:
        logger.error("Failed to load historical M1 data.")
        return None, None, None, None
        
    # Localize/Standardize timezone
    m1_df['time'] = pd.to_datetime(m1_df['time'], format='mixed', utc=True).dt.tz_localize(None)
    m1_df = m1_df.sort_values('time').reset_index(drop=True)
    
    if m5_df.empty:
        logger.info("Resampling M5 from M1 data...")
        m5_df = m1_df.set_index('time').resample('5min').agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'tick_volume': 'sum'
        }).dropna().reset_index()
    else:
        m5_df['time'] = pd.to_datetime(m5_df['time'], format='mixed', utc=True).dt.tz_localize(None)
        m5_df = m5_df.sort_values('time').reset_index(drop=True)
        
    if m15_df.empty:
        logger.info("Resampling M15 from M1 data...")
        m15_df = m1_df.set_index('time').resample('15min').agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'tick_volume': 'sum'
        }).dropna().reset_index()
    else:
        m15_df['time'] = pd.to_datetime(m15_df['time'], format='mixed', utc=True).dt.tz_localize(None)
        m15_df = m15_df.sort_values('time').reset_index(drop=True)
        
    # Resample H1 from M5 to ensure perfectly aligned timeline
    h1_df = m5_df.set_index('time').resample('1h').agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'tick_volume': 'sum'
    }).dropna().reset_index()
    
    return m1_df, m5_df, m15_df, h1_df

def run_simulation(symbol, m1_df, m5_df, m15_df, h1_df, initial_balance=10000.0):
    """Simulates the layering strategy minute-by-minute."""
    logger.info(f"Setting active configuration symbol to {symbol}...")
    btc_config.set_active_symbol(symbol)
    
    # Calculate indicators
    logger.info("Calculating technical indicators...")
    h1_df = calculate_h1_layer_indicators(h1_df)
    
    if "XAGUSD" in symbol:
        try:
            import requests
            url = "http://127.0.0.1:8081/api/dxy/historical?limit=50000"
            logger.info(f"Fetching historical DXY data from microservice: {url} ...")
            response = requests.get(url, timeout=15)
            if response.status_code == 200:
                data = response.json()
                dxy_df = pd.DataFrame(data)
                dxy_df['time'] = pd.to_datetime(dxy_df['time'], utc=True).dt.tz_localize(None)
                dxy_df = dxy_df.sort_values('time').copy()
                dxy_df['dxy_ema_200'] = dxy_df['close'].ewm(span=200, adjust=False).mean()
                dxy_df = dxy_df.rename(columns={'close': 'dxy_close'})
                h1_df = h1_df.sort_values('time')
                h1_df = pd.merge_asof(h1_df, dxy_df[['time', 'dxy_close', 'dxy_ema_200']], on='time', direction='backward')
                logger.info("Successfully fetched and merged DXY data from microservice for XAGUSD backtesting.")
            else:
                logger.error(f"Failed to fetch DXY data from microservice: HTTP {response.status_code}")
        except Exception as e:
            logger.error(f"Failed to load DXY data for XAGUSD backtest: {e}")
            
    m5_df = calculate_m1_layer_indicators(m5_df)
    m1_df = calculate_m1_layer_indicators(m1_df)
    m15_df = calculate_m1_layer_indicators(m15_df)
    
    # Extract base config values directly from raw config module to prevent live time dependency
    import importlib
    try:
        symbol_module = importlib.import_module(f"config.symbols.{symbol}")
    except ImportError:
        symbol_module = importlib.import_module("config.symbols.BTCUSDc")
        
    normal_lot_size = symbol_module.LOT_SIZE
    normal_tp_per_layer = symbol_module.TAKE_PROFIT_PER_LAYER_USD
    normal_layering_step_atr_mult = getattr(symbol_module, 'LAYERING_STEP_ATR_MULT', 1.0)
    low_risk_overrides = getattr(symbol_module, 'LOW_RISK_OVERRIDES', {})
    moderate_risk_overrides = getattr(symbol_module, 'MODERATE_RISK_OVERRIDES', {})
    
    rsi_limit_down_m1 = getattr(btc_config, 'RSI_LIMIT_DOWN_M1', 20)
    rsi_limit_up_m1 = getattr(btc_config, 'RSI_LIMIT_UP_M1', 80)
    max_layers = btc_config.MAX_LAYERS
    safety_limit = btc_config.number_of_normal_layer * btc_config.constant
    
    spec = SYMBOL_SPECS.get(symbol, {"contract_size": 1.0, "pip_size": 1.0})
    contract_size = spec["contract_size"]
    
    # Timestamps & Data indexers
    h1_times = h1_df['time'].values
    m5_times = m5_df['time'].values
    m15_times = m15_df['time'].values
    m1_times = m1_df['time'].values
    
    # Choose timeline: M5 for XAGUSD, M1 for all others
    is_xagusd = "XAGUSD" in symbol
    use_m5 = is_xagusd or "ETHUSD" in symbol
    timeline_df = m5_df if use_m5 else m1_df
    timeline_times = timeline_df['time'].values
    
    logger.info(f"Timeline starts: {timeline_times[0]} to {timeline_times[-1]}")
    logger.info(f"Total steps to simulate: {len(timeline_df)}")
    
    # Backtest state
    balance = initial_balance
    equity = initial_balance
    positions = []
    closed_trades = []
    
    # Basket tracking
    basket_direction = None
    basket_first_price = 0.0
    basket_magic = None
    
    # Daily circuit breaker tracking
    current_day = None
    daily_realized_profit = 0.0
    losing_trades_timestamps = []
    circuit_breaker_tripped = False
    
    equity_curve = []
    equity_times = []
    
    for i in range(2, len(timeline_df)):
        t_np = timeline_times[i]
        t = pd.Timestamp(t_np)
        bar = timeline_df.iloc[i]
        
        # Track daily resets for circuit breaker
        bar_date = t.date()
        if current_day is None or bar_date != current_day:
            current_day = bar_date
            daily_realized_profit = 0.0
            circuit_breaker_tripped = False
            
        # 1. Update floating PnL and Equity
        floating_pnl = 0.0
        for p in positions:
            p_pnl = (bar['close'] - p['entry_price']) * p['volume'] * contract_size if p['type'] == 'BUY' else (p['entry_price'] - bar['close']) * p['volume'] * contract_size
            floating_pnl += p_pnl
        equity = balance + floating_pnl
        equity_curve.append(equity)
        equity_times.append(t)
        
        # 2. Check position management (TP and Layering)
        if positions:
            # Basket TP Check
            if positions:
                oldest_pos = min(positions, key=lambda p: p['entry_time'])
                basket_risk = oldest_pos['risk_level']
            else:
                basket_risk = "normal"
            
            is_sunday_override = oldest_pos.get('sunday_override', False)
            
            if is_sunday_override and basket_risk == "low":
                if "BTCUSD" in symbol:
                    tp_val = 0.20
                elif "ETHUSD" in symbol:
                    tp_val = 0.02
            elif basket_risk == "normal":
                tp_val = normal_tp_per_layer
            elif basket_risk == "moderate":
                tp_val = moderate_risk_overrides.get('TAKE_PROFIT_PER_LAYER_USD', normal_tp_per_layer)
            else:
                tp_val = low_risk_overrides.get('TAKE_PROFIT_PER_LAYER_USD', normal_tp_per_layer)
                
            target_profit = tp_val * len(positions)
                
            total_volume = sum(p['volume'] for p in positions)
            weighted_entry = sum(p['entry_price'] * p['volume'] for p in positions) / total_volume
            
            if basket_direction == 'BUY':
                tp_price = weighted_entry + (target_profit / (contract_size * total_volume))
                tp_hit = bar['high'] >= tp_price
                exit_price = max(tp_price, bar['open'])
            else:
                tp_price = weighted_entry - (target_profit / (contract_size * total_volume))
                tp_hit = bar['low'] <= tp_price
                exit_price = min(tp_price, bar['open'])
                
            if tp_hit:
                # Close all positions in the basket
                basket_pnl = 0.0
                for p in positions:
                    trade_pnl = (exit_price - p['entry_price']) * p['volume'] * contract_size if p['type'] == 'BUY' else (p['entry_price'] - exit_price) * p['volume'] * contract_size
                    net_trade_pnl = trade_pnl - (btc_config.SPREAD_DEDUCTION_USD * p['volume'] * contract_size)
                    basket_pnl += net_trade_pnl
                    closed_trades.append({
                        'ticket': p['ticket'],
                        'type': p['type'],
                        'entry_time': p['entry_time'],
                        'exit_time': t,
                        'entry_price': p['entry_price'],
                        'exit_price': exit_price,
                        'pnl': net_trade_pnl,
                        'exit_reason': 'Basket TP',
                        'magic': p['magic'],
                        'basket_layers': len(positions)
                    })
                balance += basket_pnl
                daily_realized_profit += basket_pnl
                if basket_pnl < 0:
                    losing_trades_timestamps.append((t, len(positions)))
                else:
                    losing_trades_timestamps.clear()
                positions.clear()
                basket_direction = None
                continue
                
            # Safety limit check
            if len(positions) > safety_limit:
                logger.warning(f"Safety limit reached at {t}. Closing {len(positions)} positions.")
                basket_pnl = 0.0
                exit_price = bar['open']
                for p in positions:
                    trade_pnl = (exit_price - p['entry_price']) * p['volume'] * contract_size if p['type'] == 'BUY' else (p['entry_price'] - exit_price) * p['volume'] * contract_size
                    net_trade_pnl = trade_pnl - (btc_config.SPREAD_DEDUCTION_USD * p['volume'] * contract_size)
                    basket_pnl += net_trade_pnl
                    closed_trades.append({
                        'ticket': p['ticket'],
                        'type': p['type'],
                        'entry_time': p['entry_time'],
                        'exit_time': t,
                        'entry_price': p['entry_price'],
                        'exit_price': exit_price,
                        'pnl': net_trade_pnl,
                        'exit_reason': 'Safety Limit Exceeded',
                        'magic': p['magic'],
                        'basket_layers': len(positions)
                    })
                balance += basket_pnl
                daily_realized_profit += basket_pnl
                losing_trades_timestamps.append((t, len(positions)))
                positions.clear()
                basket_direction = None
                continue
                
            # Layering Grid Check
            # Fetch last completed H1 row to get ATR-based step if needed
            idx_h1 = np.searchsorted(h1_times, t_np - np.timedelta64(1, 'h'), side='right') - 1
            if idx_h1 >= 0:
                h1_row = h1_df.iloc[idx_h1]
                step = get_layer_step_val(h1_row, symbol, basket_risk, normal_layering_step_atr_mult, low_risk_overrides, moderate_risk_overrides)
            else:
                step = btc_config.LAYERING_STEP_USD
                
            # is_sunday_override and basket_risk are locked to the oldest position (first layer)
                
            if is_sunday_override and basket_risk == "low":
                current_lot_size = 0.01
            elif basket_risk == "low":
                current_lot_size = low_risk_overrides.get('LOT_SIZE', normal_lot_size)
            elif basket_risk == "moderate":
                current_lot_size = moderate_risk_overrides.get('LOT_SIZE', normal_lot_size)
            else:
                current_lot_size = normal_lot_size
            
            while True:
                k = len(positions)
                if max_layers is not None and k >= max_layers:
                    break
                    
                if basket_direction == 'BUY':
                    trigger_price = basket_first_price - k * step
                    if bar['low'] <= trigger_price:
                        entry_price = min(trigger_price, bar['open'])
                        positions.append({
                            'ticket': len(closed_trades) + len(positions) + 1,
                            'type': 'BUY',
                            'entry_time': t,
                            'entry_price': entry_price,
                            'volume': current_lot_size,
                            'risk_level': risk_level,
                            'sunday_override': is_sunday_override,
                            'magic': basket_magic
                        })
                    else:
                        break
                else: # SELL
                    trigger_price = basket_first_price + k * step
                    if bar['high'] >= trigger_price:
                        entry_price = max(trigger_price, bar['open'])
                        positions.append({
                            'ticket': len(closed_trades) + len(positions) + 1,
                            'type': 'SELL',
                            'entry_time': t,
                            'entry_price': entry_price,
                            'volume': current_lot_size,
                            'risk_level': risk_level,
                            'sunday_override': is_sunday_override,
                            'magic': basket_magic
                        })
                    else:
                        break
                        
        # 3. Check new entries (if no positions and circuit breaker not active)
        else:
            # Check Circuit Breakers
            loss_pct = 0.0 if balance <= 0 else (-daily_realized_profit) / balance
            
            # Filter losing trades to last 7 days
            cutoff_time = t - pd.Timedelta(days=7)
            recent_losses = [item for item in losing_trades_timestamps if item[0] >= cutoff_time]
            consecutive_losses = sum(item[1] for item in recent_losses)
            
            if loss_pct > 0.05 or consecutive_losses >= 5:
                circuit_breaker_tripped = True
                
            if circuit_breaker_tripped:
                continue
                
            # Find completed index values
            idx_h1 = np.searchsorted(h1_times, t_np - np.timedelta64(1, 'h'), side='right') - 1
            idx_m5 = np.searchsorted(m5_times, t_np - np.timedelta64(5, 'm'), side='right') - 1
            idx_m15 = np.searchsorted(m15_times, t_np - np.timedelta64(15, 'm'), side='right') - 1
            idx_m1 = np.searchsorted(m1_times, t_np - np.timedelta64(1, 'm'), side='right') - 1
            
            if idx_h1 < 0 or idx_m5 < 1 or idx_m15 < 1 or (not use_m5 and idx_m1 < 1):
                continue
                
            h1_row = h1_df.iloc[idx_h1]
            
            # H1 Signal
            h1_close, h1_ema = h1_row['close'], h1_row['ema_200']
            if is_xagusd:
                dxy_close = h1_row.get('dxy_close')
                dxy_ema = h1_row.get('dxy_ema_200')
                if pd.isna(dxy_close) or pd.isna(dxy_ema):
                    h1_signal = None
                else:
                    buy_ok = h1_close > h1_ema and dxy_close < dxy_ema
                    sell_ok = h1_close < h1_ema and dxy_close > dxy_ema
                    h1_signal = "BUY" if buy_ok else ("SELL" if sell_ok else None)
            else:
                h1_signal = "BUY" if h1_close > h1_ema else ("SELL" if h1_close < h1_ema else None)
                
            if h1_signal is None:
                continue
                
            # M15 Crossover Signal
            m15_curr = m15_df.iloc[idx_m15]
            m15_prev = m15_df.iloc[idx_m15 - 1]
            rsi_curr_m15 = m15_curr['rsi_14']
            rsi_prev_m15 = m15_prev['rsi_14']
            m15_buy = rsi_prev_m15 <= rsi_limit_down_m1 < rsi_curr_m15
            m15_sell = rsi_prev_m15 >= rsi_limit_up_m1 > rsi_curr_m15
            m15_signal = "BUY" if m15_buy else ("SELL" if m15_sell else None)
            
            # M5 Crossover Signal
            m5_curr = m5_df.iloc[idx_m5]
            m5_prev = m5_df.iloc[idx_m5 - 1]
            rsi_curr_m5 = m5_curr['rsi_14']
            rsi_prev_m5 = m5_prev['rsi_14']
            m5_buy = rsi_prev_m5 <= rsi_limit_down_m1 < rsi_curr_m5
            m5_sell = rsi_prev_m5 >= rsi_limit_up_m1 > rsi_curr_m5
            m5_signal = "BUY" if m5_buy else ("SELL" if m5_sell else None)
            
            # M1 Crossover Signal
            m1_signal = None
            is_ethusd = "ETHUSD" in symbol
            if not is_xagusd and not is_ethusd:
                m1_curr = m1_df.iloc[idx_m1]
                m1_prev = m1_df.iloc[idx_m1 - 1]
                rsi_curr_m1 = m1_curr['rsi_14']
                rsi_prev_m1 = m1_prev['rsi_14']
                m1_buy = rsi_prev_m1 <= rsi_limit_down_m1 < rsi_curr_m1
                m1_sell = rsi_prev_m1 >= rsi_limit_up_m1 > rsi_curr_m1
                m1_signal = "BUY" if m1_buy else ("SELL" if m1_sell else None)
                
            # Determine Trigger
            t_wib = t.tz_localize('UTC').tz_convert('Asia/Jakarta').tz_localize(None)
            risk_level = btc_config.get_risk_level(t_wib)
            
            # Check Sunday Override for BTCUSD
            weekday = t_wib.weekday()
            hour = t_wib.hour
            is_sunday_override = False
            if "BTCUSD" in symbol or "ETHUSD" in symbol:
                is_sunday_override = (weekday == 6 and 20 <= hour < 22) or (weekday == 0 and 1 <= hour < 12)
                
            if is_sunday_override and risk_level == "low":
                current_lot_size = 0.01
            elif risk_level == "low":
                current_lot_size = low_risk_overrides.get('LOT_SIZE', normal_lot_size)
            elif risk_level == "moderate":
                current_lot_size = moderate_risk_overrides.get('LOT_SIZE', normal_lot_size)
            else:
                current_lot_size = normal_lot_size
            
            # M15 gets priority
            if h1_signal == m15_signal:
                magic_num = getattr(btc_config, "MAGIC_NUMBER_M15", 20260533)
                positions.append({
                    'ticket': len(closed_trades) + 1,
                    'type': h1_signal,
                    'entry_time': t,
                    'entry_price': bar['open'],
                    'volume': current_lot_size,
                    'risk_level': risk_level,
                    'sunday_override': is_sunday_override,
                    'magic': magic_num
                })
                basket_direction = h1_signal
                basket_first_price = bar['open']
                basket_magic = magic_num
            elif h1_signal == m5_signal:
                magic_num = getattr(btc_config, "MAGIC_NUMBER_M5", btc_config.MAGIC_NUMBER)
                positions.append({
                    'ticket': len(closed_trades) + 1,
                    'type': h1_signal,
                    'entry_time': t,
                    'entry_price': bar['open'],
                    'volume': current_lot_size,
                    'risk_level': risk_level,
                    'sunday_override': is_sunday_override,
                    'magic': magic_num
                })
                basket_direction = h1_signal
                basket_first_price = bar['open']
                basket_magic = magic_num
            elif not is_xagusd and h1_signal == m1_signal:
                magic_num = btc_config.MAGIC_NUMBER
                positions.append({
                    'ticket': len(closed_trades) + 1,
                    'type': h1_signal,
                    'entry_time': t,
                    'entry_price': bar['open'],
                    'volume': current_lot_size,
                    'risk_level': risk_level,
                    'sunday_override': is_sunday_override,
                    'magic': magic_num
                })
                basket_direction = h1_signal
                basket_first_price = bar['open']
                basket_magic = magic_num
                
    return closed_trades, equity_curve, equity_times

def get_layer_step_val(h1_row, symbol, basket_risk, normal_atr_mult, low_risk_overrides, moderate_risk_overrides):
    """Gets layering step based on mode."""
    if btc_config.LAYERING_MODE == "ATR":
        atr = h1_row['atr_14'] if 'atr_14' in h1_row else (0.50 if "XAG" in symbol else 100.0)
        if basket_risk == "low":
            mult = low_risk_overrides.get('LAYERING_STEP_ATR_MULT', normal_atr_mult)
        elif basket_risk == "moderate":
            mult = moderate_risk_overrides.get('LAYERING_STEP_ATR_MULT', normal_atr_mult)
        else:
            mult = normal_atr_mult
        return atr * mult
    return btc_config.LAYERING_STEP_USD

def main():
    parser = argparse.ArgumentParser(description="Multi-Timeframe Layering Strategy Backtest")
    parser.add_argument("--symbol", type=str, default="XAUUSDc", help="Symbol to backtest")
    parser.add_argument("--limit", type=int, default=50000, help="Number of historical bars to load")
    parser.add_argument("--use-mt5", action="store_true", help="Download fresh data from MT5 terminal")
    parser.add_argument("--path", type=str, default=None, help="Path to Metatrader 5 terminal64.exe")
    parser.add_argument("--login", type=int, default=None, help="MT5 login account number")
    parser.add_argument("--password", type=str, default=None, help="MT5 login account password")
    parser.add_argument("--server", type=str, default=None, help="MT5 server name")
    args = parser.parse_args()
    
    logger.info(f"Starting backtest simulation for symbol: {args.symbol}...")
    m1_df, m5_df, m15_df, h1_df = load_data(
        args.symbol,
        use_mt5=args.use_mt5,
        limit=args.limit,
        path=args.path,
        login=args.login,
        password=args.password,
        server=args.server
    )
    
    if m1_df is None or m1_df.empty:
        logger.error("Could not run backtest due to lack of historical data.")
        return
        
    trades, equity_curve, equity_times = run_simulation(args.symbol, m1_df, m5_df, m15_df, h1_df)
    
    if not trades:
        logger.warning("Backtest completed with zero trades executed.")
        return
        
    trades_df = pd.DataFrame(trades)
    
    # Calculate statistics
    total_trades = len(trades_df)
    win_trades = trades_df[trades_df['pnl'] > 0]
    loss_trades = trades_df[trades_df['pnl'] <= 0]
    
    win_rate = (len(win_trades) / total_trades) * 100 if total_trades > 0 else 0.0
    total_pnl = trades_df['pnl'].sum()
    
    # Max Drawdown calculation
    equity_series = pd.Series(equity_curve)
    cum_max = equity_series.cummax()
    drawdown = (cum_max - equity_series) / cum_max * 100
    max_dd = drawdown.max()
    
    # Sharpe Ratio calculation (using daily returns)
    daily_equity = pd.DataFrame({'time': equity_times, 'equity': equity_curve})
    daily_equity['date'] = pd.to_datetime(daily_equity['time']).dt.date
    daily_res = daily_equity.groupby('date')['equity'].last()
    daily_pct = daily_res.pct_change().dropna()
    std = daily_pct.std()
    sharpe = (daily_pct.mean() / std * np.sqrt(252)) if std > 0 else 0.0
    
    # Convert timestamps to WIB (Asia/Jakarta) timezone
    trades_df['entry_time'] = pd.to_datetime(trades_df['entry_time']).dt.tz_localize('UTC').dt.tz_convert('Asia/Jakarta').dt.tz_localize(None)
    trades_df['exit_time'] = pd.to_datetime(trades_df['exit_time']).dt.tz_localize('UTC').dt.tz_convert('Asia/Jakarta').dt.tz_localize(None)
    equity_times_wib = pd.to_datetime(equity_times).tz_localize('UTC').tz_convert('Asia/Jakarta').tz_localize(None)
    
    print("\n" + "="*50)
    print(f"      BACKTEST RESULTS FOR {args.symbol} (WIB TIME)")
    print("="*50)
    print(f"Total Trades Closed:  {total_trades}")
    print(f"Win Rate:             {win_rate:.2f}%")
    print(f"Total Net Return:     {total_pnl:.2f} USD")
    print(f"Max Drawdown:         {max_dd:.2f}%")
    print(f"Sharpe Ratio:         {sharpe:.4f}")
    print(f"Exit Reasons:         {trades_df['exit_reason'].value_counts().to_dict()}")
    if 'basket_layers' in trades_df.columns:
        baskets_df = trades_df.groupby('exit_time').first()
        layer_dist = baskets_df['basket_layers'].value_counts().sort_index()
        print("-" * 50)
        print("Basket Size / Layer Distribution:")
        for layers, count in layer_dist.items():
            print(f"  {layers} layer(s): {count} basket(s) closed")
    print("="*50)
    
    # Plotting Equity Curve
    plt.figure(figsize=(12, 6))
    plt.plot(equity_times_wib, equity_curve, label="Strategy Equity", color="#1f77b4")
    plt.title(f"Layering Strategy Backtest Equity Curve - {args.symbol} (WIB)")
    plt.xlabel("Time (WIB)")
    plt.ylabel("Equity (USD)")
    plt.grid(True, alpha=0.3)
    plt.legend()
    
    plot_path = f"backtest_{args.symbol}_results.png"
    plt.savefig(plot_path)
    logger.info(f"Equity curve plot saved to {plot_path}")
    
    csv_path = f"backtest_{args.symbol}_trades.csv"
    trades_df.to_csv(csv_path, index=False)
    logger.info(f"Detailed trade logs saved to {csv_path}")
    
    baskets_csv_path = f"backtest_{args.symbol}_baskets.csv"
    baskets_df = trades_df.groupby('exit_time').agg(
        first_trade_open_time=('entry_time', 'min'),
        closed_time=('exit_time', 'first'),
        direction=('type', 'first'),
        total_layers=('basket_layers', 'max'),
        total_pnl=('pnl', 'sum')
    ).reset_index(drop=True)
    baskets_df.to_csv(baskets_csv_path, index=False)
    logger.info(f"Basket-level logs saved to {baskets_csv_path}")

if __name__ == "__main__":
    main()
