import sqlite3
import os

db_path = 'data/database/market_data.sqlite'
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    print(tables)
    conn.close()
else:
    print(f"Database {db_path} not found.")
