import sqlite3

conn = sqlite3.connect("menu.db")
cursor = conn.cursor()

cursor.execute("""
INSERT INTO dishes (name, description, photo, category)
VALUES (?, ?, ?, ?)
""", (
    "Паста Карбонара",
    "Сливочный соус, бекон, сыр",
    "photos/carbonara.jpg",
    "pasta"
))

conn.commit()
conn.close()

print("Добавлено")