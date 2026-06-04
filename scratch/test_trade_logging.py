import sys
import os
from unittest.mock import patch
import sqlite3
import numpy as np

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.trade_logger import TradeRsiLogger

@patch('MetaTrader5.copy_rates_from_pos')
def run_manual_test(mock_copy_rates):
    # Mocking rates returned by mt5
    dtype = [('time', 'i8'), ('open', 'f8'), ('high', 'f8'), ('low', 'f8'), ('close', 'f8'), 
             ('tick_volume', 'i8'), ('spread', 'i8'), ('real_volume', 'i8')]
    mock_rates = [(1700000000 + i, 10.0, 12.0, 9.0, 10.0 + i, 10, 1, 0) for i in range(150)]
    rates_array = np.array(mock_rates, dtype=dtype)
    mock_copy_rates.return_value = rates_array

    db_path = "data/database/market_data.sqlite"
    print(f"Initializing TradeRsiLogger with database at: {db_path}")
    logger = TradeRsiLogger(db_path=db_path)

    ticket = 12345678
    action = "BUY"
    symbol = "BTCUSDc"
    price = 68000.50
    volume = 0.12

    print(f"Logging trade: ticket={ticket}, action={action}, symbol={symbol}, price={price}, volume={volume}")
    logger.log_trade(ticket, action, symbol, price, volume)

    print("Verifying database insertion...")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Print schema
    cursor.execute("PRAGMA table_info(trade_rsi_log)")
    columns = cursor.fetchall()
    print("\nTable Schema (trade_rsi_log):")
    for col in columns:
        print(f"  {col[1]} ({col[2]})")

    # Fetch inserted row
    cursor.execute("SELECT * FROM trade_rsi_log WHERE ticket = ?", (ticket,))
    row = cursor.fetchone()
    
    # Clean up the test row
    cursor.execute("DELETE FROM trade_rsi_log WHERE ticket = ?", (ticket,))
    conn.commit()
    conn.close()

    if row:
        print("\nInserted Row Details:")
        print(f"  ID: {row[0]}")
        print(f"  Timestamp: {row[1]}")
        print(f"  Ticket: {row[2]}")
        print(f"  Action: {row[3]}")
        print(f"  Symbol: {row[4]}")
        print(f"  Price: {row[5]}")
        print(f"  Volume: {row[6]}")
        print(f"  RSI M1: {row[7]:.4f}")
        print(f"  RSI M5: {row[8]:.4f}")
        print(f"  RSI M15: {row[9]:.4f}")
        print(f"  RSI M30 (rsi_30): {row[10]:.4f}")
        print(f"  RSI H1: {row[11]:.4f}")
        print(f"  RSI H4: {row[12]:.4f}")
        print(f"  RSI D1: {row[13]:.4f}")
        print(f"  RSI W1: {row[14]:.4f}")
        print("\nVerification SUCCESSFUL!")
    else:
        print("\nVerification FAILED: Row not found.")
        sys.exit(1)

if __name__ == "__main__":
    run_manual_test()
