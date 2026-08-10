import sqlite3
import os

def main():
    db_path = "data/database/market_data.sqlite"
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return
        
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    print("Tables in database:")
    for t in tables:
        print(t[0])
    conn.close()

if __name__ == "__main__":
    main()
