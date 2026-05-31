import sqlite3

conn = sqlite3.connect("menu.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS dishes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    description TEXT,
    photo TEXT,
    category TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_name TEXT,
    dish_name TEXT
)
""")

conn.commit()
conn.close()