import sqlite3

conn = sqlite3.connect("data/database/market_data.sqlite")
cursor = conn.cursor()

# Drop XAUUSDc_5 table to force resampling from M1 data
try:
    cursor.execute("DROP TABLE IF EXISTS XAUUSDc_5;")
    print("Dropped table XAUUSDc_5")
except Exception as e:
    print("Error dropping XAUUSDc_5:", e)

# Also drop BTCUSDc_5 table to force resampling if needed
try:
    cursor.execute("DROP TABLE IF EXISTS BTCUSDc_5;")
    print("Dropped table BTCUSDc_5")
except Exception as e:
    print("Error dropping BTCUSDc_5:", e)

conn.commit()
conn.close()
print("Done!")
