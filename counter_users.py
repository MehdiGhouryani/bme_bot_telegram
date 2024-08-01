import sqlite3
def count_unique_users():
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM users')
    count = cursor.fetchone()[0]
    conn.close()
    return count

print(f"تعداد کاربران   :  {count_unique_users()}")