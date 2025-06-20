import sqlite3
import pandas as pd

# Load your CSV
df = pd.read_csv("loyalty.csv")

# Drop the extra index column if it exists
if 'Unnamed: 0' in df.columns:
    df = df.drop(columns=['Unnamed: 0'])

# Connect to SQLite
conn = sqlite3.connect("hotel_data.db")
cursor = conn.cursor()

# Drop the existing table if it exists
cursor.execute("DROP TABLE IF EXISTS loyalty_bookings")

# Create table to match your CSV structure
cursor.execute("""
CREATE TABLE loyalty_bookings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guest_name TEXT,
    goal TEXT,
    loyalty_tier TEXT,
    preferred_room TEXT,
    booking_date TEXT,
    base_price REAL,
    loyalty_discount REAL,
    final_price REAL
)
""")

# Insert data from DataFrame
df.to_sql("loyalty_bookings", conn, if_exists="append", index=False)

conn.commit()
conn.close()

print("✅ loyalty.csv data loaded into SQLite successfully.")
