import sqlite3

# 建立資料庫連線（如果檔案不存在會自動建立）
conn = sqlite3.connect("example.db")
cursor = conn.cursor()

# 建立一個資料表
cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL
)
''')

# 新增一筆資料
cursor.execute("INSERT INTO users (name) VALUES (?)", ("Alice",))
conn.commit()

# 查詢資料
cursor.execute("SELECT * FROM users")
rows = cursor.fetchall()
print("Users:", rows)

# 關閉連線
conn.close()
