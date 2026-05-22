import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import sqlite3
import pandas as pd
from data.storage import DataStorage

storage = DataStorage()
with sqlite3.connect(storage.db_path) as conn:
    df = pd.read_sql("SELECT * FROM BTCUSD_1 LIMIT 1", conn)
    print(df.columns.tolist())
    print(df.head())
