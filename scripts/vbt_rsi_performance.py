import sys
import os
import pandas as pd

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.storage import DataStorage
from strategies.vbt_rsi_breakout import VBTrsiBreakout
from monitoring.logger import setup_logging
from config.credentials import get_mt5_credentials

def main():
    logger = setup_logging()
    logger.info("Generating Performance Report for RSI Breakout Strategy...")

    credentials = get_mt5_credentials()
    symbol = credentials.get('symbol', 'BTCUSDc')
    
    storage = DataStorage()
    df = storage.load_rates(symbol, 1, limit=50000)
    
    if df.empty:
        logger.error("No data found in database.")
        return
        
    df['time'] = pd.to_datetime(df['time'])
    df = df.sort_values('time').set_index('time')
    
    # Initialize VBT RSI Breakout strategy
    strategy = VBTrsiBreakout(rsi_window=14)
    
    # Run backtest
    portfolio = strategy.backtest(
        df['close'], 
        open_price=df['open'],
        init_cash=10000,
        fees=0.0006, # 0.06% fees
        slippage=0.0001,
        freq='1m', # Set frequency here for stats calculation
        tp_stop=0.002 # Take profit at 0.2%
    )
    
    stats = portfolio.stats()
    
    print("\n" + "="*50)
    print("      RSI BREAKOUT PERFORMANCE REPORT")
    print("="*50)
    
    print(f"Start Date:           {df.index.min()}")
    print(f"End Date:             {df.index.max()}")
    print("-" * 50)
    print(f"Total Return [%]:      {portfolio.total_return() * 100:.2f}%")
    print(f"MAX DRAWDOWN [%]:      {stats.get('Max Drawdown [%]', 0):.2f}%")
    print(f"SHARPE RATIO:          {stats.get('Sharpe Ratio', 0):.4f}")
    print("-" * 50)
    print(f"Total Trades:         {stats.get('Total Trades', 0)}")
    print(f"Win Rate [%]:          {stats.get('Win Rate [%]', 0):.2f}%")
    print(f"Profit Factor:         {stats.get('Profit Factor', 0):.4f}")
    print("="*50)

if __name__ == "__main__":
    main()
