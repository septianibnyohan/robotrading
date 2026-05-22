import sys
import os
import pandas as pd
import matplotlib.pyplot as plt

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data.storage import DataStorage
from strategies.sma_momentum import SMAMomentumStrategy
from monitoring.logger import setup_logging

def main():
    logger = setup_logging()
    logger.info("Starting Visual Signal Audit...")

    storage = DataStorage()
    # Use a smaller window (last 500 bars) for better visibility
    df = storage.load_rates('BTCUSD', 1, limit=500)
    
    if df.empty:
        logger.error("No data found.")
        return
        
    df = df.sort_values('time').reset_index(drop=True)
    strategy = SMAMomentumStrategy()
    df = strategy.generate_signals(df)
    
    # --- Plotting ---
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(15, 10), sharex=True, gridspec_kw={'height_ratios': [3, 1]})
    
    # 1. Price and SMAs
    ax1.plot(df['time'], df['close'], label='Price', color='black', alpha=0.5)
    ax1.plot(df['time'], df['sma_fast'], label='SMA 10 (Fast)', color='blue', linestyle='--')
    ax1.plot(df['time'], df['sma_slow'], label='SMA 50 (Slow)', color='orange', linestyle='--')
    
    # Signals
    buy_signals = df[df['signal'] == 1]
    sell_signals = df[df['signal'] == -1]
    
    ax1.scatter(buy_signals['time'], buy_signals['close'], marker='^', color='green', s=100, label='BUY')
    ax1.scatter(sell_signals['time'], sell_signals['close'], marker='v', color='red', s=100, label='SELL')
    
    ax1.set_title('BTCUSD Price Action & Strategy Signals (Audit)')
    ax1.set_ylabel('Price (USD)')
    ax1.legend()
    ax1.grid(True, alpha=0.2)
    
    # 2. RSI
    ax2.plot(df['time'], df['rsi'], label='RSI 14', color='purple')
    ax2.axhline(70, color='red', linestyle=':', alpha=0.5)
    ax2.axhline(30, color='green', linestyle=':', alpha=0.5)
    ax2.axhline(85, color='darkred', linestyle='-', alpha=0.3, label='Exhaustion (85)')
    
    ax2.set_ylabel('RSI')
    ax2.set_ylim(0, 100)
    ax2.legend()
    ax2.grid(True, alpha=0.2)
    
    plt.tight_layout()
    plot_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'visual_audit.png')
    plt.savefig(plot_path)
    logger.info(f"Visual audit chart saved to {plot_path}")

if __name__ == "__main__":
    main()
