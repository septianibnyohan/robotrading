import sqlite3
import pandas as pd

conn = sqlite3.connect("data/database/market_data.sqlite")
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = cursor.fetchall()
print("Tables in database:")
for t in tables:
    name = t[0]
    cursor.execute(f"SELECT COUNT(*), MIN(time), MAX(time) FROM {name};")
    cnt, min_t, max_t = cursor.fetchone()
    print(f"Table: {name} | Count: {cnt} | Min Time: {min_t} | Max Time: {max_t}")
conn.close()
