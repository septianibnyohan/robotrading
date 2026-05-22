import sqlite3
import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime, timezone

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from strategies.rsi_ema_50_cross_scalper import RsiEma50CrossScalperStrategy

def run_backtest(db_path="data/database/market_data.sqlite", table_name="XAUUSDc_1", 
                 fast_ema=5, slow_ema=13, rsi_period=7, min_atr=0.8, 
                 rr=1.5, use_atr_sl=True, fixed_sl_pips=5.0, max_hold_min=10, 
                 use_trail=True, lot_size=0.01, commission_per_trade=0.07, slippage_pips=1.0,
                 ema_trend_mult=0.5):
    
    # 1. Load data from database
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return None
        
    conn = sqlite3.connect(db_path)
    df = pd.read_sql_query(f"SELECT * FROM {table_name} ORDER BY time ASC", conn)
    conn.close()
    
    if df.empty:
        print("No historical data found in database.")
        return None
        
    print(f"Loaded {len(df)} bars of historical data for backtesting.")
    
    # 2. Convert time column
    df['time'] = pd.to_datetime(df['time'])
    
    # 3. Calculate indicators using strategy
    strategy = RsiEma50CrossScalperStrategy(
        fast_ema_period=fast_ema,
        slow_ema_period=slow_ema,
        rsi_period=rsi_period,
        min_atr=min_atr
    )
    
    df = strategy.calculate_indicators(df)
    
    # Pre-calculate entry signals
    # We must shift signals by 1 to represent "decide at close, execute at next open"
    df['prev_rsi'] = df['rsi'].shift(1)
    df['volatility_ok'] = df['atr'] > min_atr
    df['ema_trend_ok'] = (df['fast_ema'] - df['slow_ema']).abs() > ema_trend_mult * df['atr']
    
    df['long_signal'] = (
        df['volatility_ok'] &
        df['ema_trend_ok'] &
        (df['fast_ema'] > df['slow_ema']) &
        (df['prev_rsi'] <= strategy.rsi_level) & (df['rsi'] > strategy.rsi_level) &
        (df['close'] > df['fast_ema'])
    ).fillna(False)
    
    df['short_signal'] = (
        df['volatility_ok'] &
        df['ema_trend_ok'] &
        (df['fast_ema'] < df['slow_ema']) &
        (df['prev_rsi'] >= strategy.rsi_level) & (df['rsi'] < strategy.rsi_level) &
        (df['close'] < df['fast_ema'])
    ).fillna(False)

    # 4. Simulate trading bar-by-bar
    trades = []
    active_position = None  # None or dict
    cooldown_until = None
    
    pip_size = 0.10 # 1 pip = 0.10 USD for XAUUSD
    slippage_price = slippage_pips * pip_size
    
    # Convert columns to lists/numpy arrays for 100x speedup
    times = df['time'].tolist()
    opens = df['open'].to_numpy()
    highs = df['high'].to_numpy()
    lows = df['low'].to_numpy()
    closes = df['close'].to_numpy()
    atrs = df['atr'].to_numpy()
    long_signals = df['long_signal'].to_numpy()
    short_signals = df['short_signal'].to_numpy()
    
    for i in range(1, len(df)):
        current_time = times[i]
        current_open = opens[i]
        current_high = highs[i]
        current_low = lows[i]
        current_close = closes[i]
        
        prev_close = closes[i-1]
        prev_atr = atrs[i-1]
        prev_long_signal = long_signals[i-1]
        prev_short_signal = short_signals[i-1]
        
        # Check active position exit first
        if active_position is not None:
            pos = active_position
            
            # Trailing Stop updates
            if use_trail:
                if pos['type'] == 'BUY':
                    price_move = prev_close - pos['entry_price']
                    if price_move >= 2.0 * pos['initial_sl_dist']:
                        new_sl = prev_close - 0.5 * pos['initial_sl_dist']
                        if new_sl > pos['sl']:
                            pos['sl'] = new_sl
                elif pos['type'] == 'SELL':
                    price_move = pos['entry_price'] - prev_close
                    if price_move >= 2.0 * pos['initial_sl_dist']:
                        new_sl = prev_close + 0.5 * pos['initial_sl_dist']
                        if pos['sl'] == 0 or new_sl < pos['sl']:
                            pos['sl'] = new_sl
            
            exit_triggered = False
            exit_price = None
            exit_reason = None
            
            # Check holding time (Time Stop)
            holding_bars = i - pos['entry_index']
            if holding_bars >= max_hold_min:
                exit_triggered = True
                exit_reason = "Time Stop"
                exit_price = current_open  # Exit at next open price
                
            # Check Stop Loss / Take Profit on the current bar's High/Low
            else:
                if pos['type'] == 'BUY':
                    if current_low <= pos['sl']:
                        exit_triggered = True
                        exit_reason = "Stop Loss"
                        exit_price = pos['sl']
                    elif current_high >= pos['tp']:
                        exit_triggered = True
                        exit_reason = "Take Profit"
                        exit_price = pos['tp']
                elif pos['type'] == 'SELL':
                    if pos['sl'] > 0 and current_high >= pos['sl']:
                        exit_triggered = True
                        exit_reason = "Stop Loss"
                        exit_price = pos['sl']
                    elif current_low <= pos['tp']:
                        exit_triggered = True
                        exit_reason = "Take Profit"
                        exit_price = pos['tp']
            
            if exit_triggered:
                # Apply slippage on exit
                if pos['type'] == 'BUY':
                    final_exit_price = exit_price - slippage_price
                    gross_pnl = (final_exit_price - pos['entry_price']) * lot_size * 100
                else:
                    final_exit_price = exit_price + slippage_price
                    gross_pnl = (pos['entry_price'] - final_exit_price) * lot_size * 100
                
                net_pnl = gross_pnl - commission_per_trade
                
                trades.append({
                    'type': pos['type'],
                    'entry_time': pos['entry_time'],
                    'entry_price': pos['entry_price'],
                    'exit_time': current_time,
                    'exit_price': final_exit_price,
                    'exit_reason': exit_reason,
                    'pnl': net_pnl,
                    'hold_time_min': holding_bars
                })
                
                # If hit Stop Loss, set 3-candle cooldown starting from this candle
                if exit_reason == "Stop Loss":
                    cooldown_until = current_time + pd.Timedelta(minutes=4)
                    
                active_position = None
                
        # Check entries if no active position and not in cooldown
        if active_position is None:
            if cooldown_until is not None and current_time < cooldown_until:
                continue
                
            # Signal is generated on prev_bar (completed candle) and executed on current_bar open
            is_long = prev_long_signal
            is_short = prev_short_signal
            
            if is_long or is_short:
                entry_type = 'BUY' if is_long else 'SELL'
                
                # Apply slippage on entry
                if entry_type == 'BUY':
                    entry_price = current_open + slippage_price
                    sl_dist = prev_atr * 1.5 if use_atr_sl else fixed_sl_pips * pip_size
                    tp_dist = sl_dist * rr
                    tp_dist = min(tp_dist, 15.0 * pip_size)  # Cap TP at 15 pips (1.50 USD)
                    sl = entry_price - sl_dist
                    tp = entry_price + tp_dist
                else:
                    entry_price = current_open - slippage_price
                    sl_dist = prev_atr * 1.5 if use_atr_sl else fixed_sl_pips * pip_size
                    tp_dist = sl_dist * rr
                    tp_dist = min(tp_dist, 15.0 * pip_size)  # Cap TP at 15 pips (1.50 USD)
                    sl = entry_price + sl_dist
                    tp = entry_price - tp_dist
                
                # Immediately check if entry bar triggers exits
                exit_triggered = False
                exit_price = None
                exit_reason = None
                
                if entry_type == 'BUY':
                    if current_low <= sl:
                        exit_triggered = True
                        exit_reason = "Stop Loss"
                        exit_price = sl
                    elif current_high >= tp:
                        exit_triggered = True
                        exit_reason = "Take Profit"
                        exit_price = tp
                else:
                    if current_high >= sl:
                        exit_triggered = True
                        exit_reason = "Stop Loss"
                        exit_price = sl
                    elif current_low <= tp:
                        exit_triggered = True
                        exit_reason = "Take Profit"
                        exit_price = tp
                
                if exit_triggered:
                    if entry_type == 'BUY':
                        final_exit_price = exit_price - slippage_price
                        gross_pnl = (final_exit_price - entry_price) * lot_size * 100
                    else:
                        final_exit_price = exit_price + slippage_price
                        gross_pnl = (entry_price - final_exit_price) * lot_size * 100
                    
                    net_pnl = gross_pnl - commission_per_trade
                    
                    trades.append({
                        'type': entry_type,
                        'entry_time': current_time,
                        'entry_price': entry_price,
                        'exit_time': current_time,
                        'exit_price': final_exit_price,
                        'exit_reason': exit_reason,
                        'pnl': net_pnl,
                        'hold_time_min': 0
                    })
                    
                    if exit_reason == "Stop Loss":
                        cooldown_until = current_time + pd.Timedelta(minutes=4)
                else:
                    active_position = {
                        'type': entry_type,
                        'entry_time': current_time,
                        'entry_price': entry_price,
                        'entry_index': i,
                        'sl': sl,
                        'tp': tp,
                        'initial_sl_dist': sl_dist
                    }

    # 5. Calculate statistics
    if not trades:
        print("No trades were executed in the backtest.")
        return None
        
    trades_df = pd.DataFrame(trades)
    
    total_trades = len(trades_df)
    winning_trades = trades_df[trades_df['pnl'] > 0]
    losing_trades = trades_df[trades_df['pnl'] <= 0]
    
    win_rate = (len(winning_trades) / total_trades) * 100
    
    gross_profit = winning_trades['pnl'].sum()
    gross_loss = abs(losing_trades['pnl'].sum())
    
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
    
    # Calculate max consecutive losses
    consecutive_losses = 0
    max_consecutive_losses = 0
    for pnl in trades_df['pnl']:
        if pnl <= 0:
            consecutive_losses += 1
            max_consecutive_losses = max(max_consecutive_losses, consecutive_losses)
        else:
            consecutive_losses = 0
            
    avg_hold_time = trades_df['hold_time_min'].mean()
    net_return = trades_df['pnl'].sum()
    
    print("\n--- Backtest Results ---")
    print(f"Total Trades: {total_trades}")
    print(f"Win Rate: {win_rate:.2f}%")
    print(f"Profit Factor: {profit_factor:.2f}")
    print(f"Max Consecutive Losses: {max_consecutive_losses}")
    print(f"Average Hold Time: {avg_hold_time:.2f} minutes")
    print(f"Net Return: {net_return:.2f} USD (with {lot_size} lots)")
    print(f"Exit Reasons: {trades_df['exit_reason'].value_counts().to_dict()}")
    print("------------------------")
    
    return {
        'total_trades': total_trades,
        'win_rate': win_rate,
        'profit_factor': profit_factor,
        'max_consecutive_losses': max_consecutive_losses,
        'avg_hold_time': avg_hold_time,
        'net_return': net_return
    }

if __name__ == "__main__":
    run_backtest()
