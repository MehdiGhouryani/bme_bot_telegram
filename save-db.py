import sqlite3

# اطلاعات به صورت دیکشنری برای ساده‌سازی
data = {
    "name":"tonometer",
    "definition": """

""",
    "types": """

""",
    "structure": """

""",
    "operation": """

""",
    "advantages_disadvantages": """

""",
    "safety": """

""",
    "related_technologies": """

""",
    "photo_path": "image/tonometer.jpg"  # مسیر فایل عکس
}

def create_table():
    conn = sqlite3.connect('example.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS information (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            definition TEXT,
            types TEXT,
            structure TEXT,
            operation TEXT,
            advantages_disadvantages TEXT,
            safety TEXT,
            related_technologies TEXT,
            photo BLOB
        )
    ''')
    conn.commit()
    conn.close()

def read_image_as_binary(photo_path):
    with open(photo_path, 'rb') as file:
        return file.read()

def insert_data(data):
    photo_binary = read_image_as_binary(data['photo_path'])
    
    conn = sqlite3.connect('example.db')
    c = conn.cursor()
    c.execute('''
        INSERT INTO information (name, definition, types, structure, operation, 
                                 advantages_disadvantages, safety, related_technologies, photo)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (data['name'], data['definition'], data['types'], data['structure'], 
          data['operation'], data['advantages_disadvantages'], data['safety'], 
          data['related_technologies'], photo_binary))
    conn.commit()
    conn.close()

if __name__ == "__main__":
    create_table()  # اطمینان حاصل کنید که جدول وجود دارد
    insert_data(data)  # اطلاعات را به پایگاه داده اضافه کنید