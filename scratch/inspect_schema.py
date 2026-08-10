import sqlite3
import os

def main():
    db_path = "data/database/market_data.sqlite"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(BTCUSDc_16385)")
    info = cursor.fetchall()
    print("Table columns:")
    for col in info:
        print(col)
        
    cursor.execute("SELECT * FROM BTCUSDc_16385 LIMIT 2")
    rows = cursor.fetchall()
    print("Sample rows:")
    for r in rows:
        print(r)
    conn.close()

if __name__ == "__main__":
    main()
