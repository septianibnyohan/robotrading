import sys
import os
import pandas as pd
import vectorbt as vbt

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.storage import DataStorage
from strategies.vbt_strategy import VBTsmaMomentum
from monitoring.logger import setup_logging
from config.credentials import get_mt5_credentials

def main():
    logger = setup_logging()
    logger.info("Generating Performance Report using VectorBT...")

    credentials = get_mt5_credentials()
    symbol = credentials.get('symbol', 'BTCUSDm')
    
    storage = DataStorage()
    # Load data from SQLite
    df = storage.load_rates(symbol, 1, limit=50000)
    
    if df.empty:
        logger.error("No data found in database. Please run the harvester first.")
        return
        
    df['time'] = pd.to_datetime(df['time'])
    df = df.sort_values('time').set_index('time')
    
    # Initialize VBT strategy
    strategy = VBTsmaMomentum(fast_window=10, slow_window=50, rsi_window=14)
    
    # Run backtest
    # We use 'close' for signals and 'open' for next-bar execution to prevent lookahead bias
    portfolio = strategy.backtest(
        df['close'], 
        open_price=df['open'],
        init_cash=10000,
        fees=0.0006, # 0.06% fees
        slippage=0.0001,
        freq='1m', # Set frequency here for stats calculation
        tp_stop=0.002 # Take profit at 0.2%
    )

    
    # Day 108: Detailed Performance Stats
    stats = portfolio.stats()
    
    print("\n" + "="*50)
    print("      STRATEGY PERFORMANCE REPORT (VectorBT)")
    print("="*50)
    
    # Focus on Max Drawdown and Sharpe Ratio as requested
    print(f"Start Date:           {df.index.min()}")
    print(f"End Date:             {df.index.max()}")
    print(f"Total Duration:       {df.index.max() - df.index.min()}")
    print("-" * 50)
    print(f"Initial Capital:      ${portfolio.init_cash:,.2f}")
    print(f"End Value:            ${portfolio.value().iloc[-1]:,.2f}")
    print(f"Total Return [%]:      {portfolio.total_return() * 100:.2f}%")
    print(f"Benchmark Return [%]:  {portfolio.total_benchmark_return() * 100:.2f}%")
    print("-" * 50)
    
    # HIGHLIGHTED METRICS
    print(f"MAX DRAWDOWN [%]:      {stats.get('Max Drawdown [%]', 0):.2f}%")
    print(f"SHARPE RATIO:          {stats.get('Sharpe Ratio', 0):.4f}")
    print(f"SORTINO RATIO:         {stats.get('Sortino Ratio', 0):.4f}")
    print("-" * 50)
    
    print(f"Total Trades:         {stats['Total Trades']}")
    print(f"Win Rate [%]:          {stats['Win Rate [%]']:.2f}%")
    print(f"Profit Factor:         {stats['Profit Factor']:.4f}")
    print(f"Expectancy:           ${stats['Expectancy']:.2f}")
    print("="*50)

    # Save full stats to a file
    stats_path = "monitoring/performance_stats.txt"
    with open(stats_path, "w") as f:
        f.write(str(stats))
    logger.info(f"Full stats saved to {stats_path}")

if __name__ == "__main__":
    main()
