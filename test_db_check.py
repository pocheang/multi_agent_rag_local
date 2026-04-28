import sqlite3

conn = sqlite3.connect("data/app.db")
conn.row_factory = sqlite3.Row

# 查看用户状态
users = conn.execute("SELECT user_id, username, status FROM users").fetchall()
print("Users:")
for u in users:
    print(f"  {u['username']}: {u['status']}")

# 查看 session
sessions = conn.execute("""
    SELECT s.token, s.user_id, u.username, u.status
    FROM auth_sessions s
    JOIN users u ON u.user_id = s.user_id
""").fetchall()
print("\nSessions:")
for s in sessions:
    print(f"  {s['username']}: status={s['status']}, token={s['token'][:20]}...")

conn.close()
