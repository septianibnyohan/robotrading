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
    logger.info("Starting Visual Reporting Dashboard Generation (Days 132-135)...")

    credentials = get_mt5_credentials()
    symbol = credentials.get('symbol', 'BTCUSDm')
    
    storage = DataStorage()
    df = storage.load_rates(symbol, 1, limit=10000)
    
    if df.empty:
        logger.error("No data found. Please ensure database has data.")
        return
        
    df['time'] = pd.to_datetime(df['time'])
    df = df.sort_values('time').set_index('time')
    
    # 1. Run Strategy Backtest
    strategy = VBTsmaMomentum(fast_window=10, slow_window=50, rsi_window=14)
    portfolio = strategy.backtest(
        df['close'], 
        open_price=df['open'],
        init_cash=10000,
        fees=0.0006,
        freq='1m'
    )
    
    # 2. Generate Interactive Plotly Dashboard
    logger.info("Generating comprehensive portfolio plot...")
    
    # pf.plot() by default includes equity curve, underwater chart, and trade markers on price
    fig = portfolio.plot(
        title="BTCUSD SMA Momentum Strategy Dashboard",
        width=1200,
        height=800
    )
    
    # 3. Save Dashboard to HTML
    output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "monitoring")
    os.makedirs(output_dir, exist_ok=True)
    
    html_path = os.path.join(output_dir, "strategy_dashboard.html")
    fig.write_html(html_path)
    
    logger.info(f"Interactive dashboard successfully saved to: {html_path}")
    print("\n" + "="*60)
    print("           VISUAL REPORTING GENERATED")
    print("="*60)
    print(f"Dashboard saved to: {html_path}")
    print("Open this file in your web browser to explore:")
    print(" - Interactive Equity Curve")
    print(" - Underwater (Drawdown) Chart")
    print(" - Trade Markers (Entries/Exits) on Price Chart")
    print("="*60)

if __name__ == "__main__":
    main()
