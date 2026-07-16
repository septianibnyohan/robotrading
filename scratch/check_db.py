import sqlite3

db_path = "data/database/market_data.sqlite"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
for table in ['BTCUSD_1', 'BTCUSDc_1', 'BTCUSDc_5', 'XAUUSDc_1', 'XAUUSDc_5']:
    try:
        cursor.execute(f"SELECT COUNT(*) FROM {table};")
        print(f"Table {table}: {cursor.fetchone()[0]} rows")
    except Exception as e:
        print(f"Error checking {table}: {e}")
conn.close()
