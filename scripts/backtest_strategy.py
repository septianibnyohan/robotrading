import sys
import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data.storage import DataStorage
from strategies.sma_momentum import SMAMomentumStrategy
from monitoring.logger import setup_logging

def main():
    logger = setup_logging()
    logger.info("Starting Strategy Backtest...")

    storage = DataStorage()
    # Load 100,000 M1 bars for a robust test
    df = storage.load_rates('BTCUSD', 1, limit=100000)
    
    if df.empty:
        logger.error("No data found for backtesting.")
        return
        
    df['time'] = pd.to_datetime(df['time'])
    df = df.sort_values('time').reset_index(drop=True)
    
    strategy = SMAMomentumStrategy(fast_window=10, slow_window=50, rsi_window=14)
    results = strategy.generate_signals(df)
    
    # --- Backtest Logic ---
    # We enter at the CLOSE of the signal bar, so we get the return of the NEXT bar.
    results['market_return'] = results['close'].pct_change().shift(-1)
    
    # Track current position (1 for Long, 0 for Flat)
    results['position'] = 0
    curr_pos = 0
    
    # Simplistic loop to handle position state based on signals
    # 1: Open Long, -1: Close Long
    positions = []
    for signal in results['signal']:
        if signal == 1:
            curr_pos = 1
        elif signal == -1:
            curr_pos = 0
        positions.append(curr_pos)
    
    results['position'] = positions
    
    # Strategy Return
    results['strategy_return'] = results['position'] * results['market_return']
    
    # Cumulative Returns
    results['cum_market_return'] = (1 + results['market_return'].fillna(0)).cumprod()
    results['cum_strategy_return'] = (1 + results['strategy_return'].fillna(0)).cumprod()
    
    # Stats
    total_return = (results['cum_strategy_return'].iloc[-1] - 1) * 100
    market_return = (results['cum_market_return'].iloc[-1] - 1) * 100
    
    logger.info(f"Backtest Complete.")
    logger.info(f"Total Strategy Return: {total_return:.2f}%")
    logger.info(f"Total Market Return (Buy & Hold): {market_return:.2f}%")
    
    # --- Plotting ---
    plt.figure(figsize=(12, 7))
    plt.plot(results['time'], results['cum_market_return'], label='Market (BTCUSD)', alpha=0.6)
    plt.plot(results['time'], results['cum_strategy_return'], label='Strategy (SMA+RSI)', linewidth=2)
    plt.title('BTCUSD Strategy Backtest: SMA 10/50 + RSI 14')
    plt.xlabel('Time')
    plt.ylabel('Cumulative Return (Base 1.0)')
    plt.legend()
    plt.grid(True, alpha=0.3)
    
    plot_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'backtest_results.png')
    plt.savefig(plot_path)
    logger.info(f"Backtest chart saved to {plot_path}")

if __name__ == "__main__":
    main()
