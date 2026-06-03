import sqlite3
from datetime import datetime
from typing import List, Dict

DB_FILE = "bot_memory.db"

def init_db():
    """Создаёт таблицу если нет"""
    conn = sqlite3.connect(DB_FILE)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()
    print("✅ База данных готова")

def get_history(limit: int = 50) -> List[Dict]:
    """Получает последние сообщения"""
    conn = sqlite3.connect(DB_FILE)
    rows = conn.execute(
        'SELECT role, content, timestamp FROM messages ORDER BY id DESC LIMIT ?', 
        (limit,)
    ).fetchall()
    conn.close()
    return [
        {"role": r[0], "content": r[1], "timestamp": r[2]} 
        for r in reversed(rows)
    ]

def save_message(role: str, content: str):
    """Сохраняет сообщение"""
    conn = sqlite3.connect(DB_FILE)
    conn.execute(
        'INSERT INTO messages (role, content) VALUES (?, ?)', 
        (role, content)
    )
    conn.commit()
    conn.close()

def clear_history():
    """Очищает историю"""
    conn = sqlite3.connect(DB_FILE)
    conn.execute('DELETE FROM messages')
    conn.commit()
    conn.close()


    