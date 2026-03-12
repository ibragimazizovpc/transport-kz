import sqlite3

conn = sqlite3.connect("database.db")

conn.execute("""
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE,
    password TEXT,
    avatar TEXT
)
""")

conn.execute("""
CREATE TABLE ads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT,
    price TEXT,
    year TEXT,
    city TEXT,
    description TEXT,
    phone TEXT,
    user_id INTEGER,
    views INTEGER DEFAULT 0
)
""")

conn.execute("""
CREATE TABLE ad_images (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ad_id INTEGER,
    filename TEXT
)
""")

conn.execute("""
CREATE TABLE favorites (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    ad_id INTEGER
)
""")

conn.execute("""
CREATE TABLE messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ad_id INTEGER,
    sender_id INTEGER,
    receiver_id INTEGER,
    text TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

conn.close()

print("Database created")