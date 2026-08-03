import sqlite3
from datetime import datetime

DB_NAME = "pontaj.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS pontaje (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        username TEXT NOT NULL,
        start_time TEXT NOT NULL,
        stop_time TEXT,
        total_minutes INTEGER
    )
    """)
    conn.commit()
    conn.close()
    print("✅ Baza de date a fost inițializată.")

def start_pontaj(user_id: int, username: str) -> bool:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute("SELECT id FROM pontaje WHERE user_id = ? AND stop_time IS NULL", (user_id,))
    if cursor.fetchone():
        conn.close()
        return False

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
        INSERT INTO pontaje (user_id, username, start_time)
        VALUES (?, ?, ?)
    """, (user_id, username, now_str))
    
    conn.commit()
    conn.close()
    return True

def stop_pontaj(user_id: int) -> int | None:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, start_time FROM pontaje WHERE user_id = ? AND stop_time IS NULL", (user_id,))
    record = cursor.fetchone()
    
    if not record:
        conn.close()
        return None
    
    pontaj_id, start_str = record
    start_dt = datetime.strptime(start_str, "%Y-%m-%d %H:%M:%S")
    end_dt = datetime.now()
    end_str = end_dt.strftime("%Y-%m-%d %H:%M:%S")
    
    duration = end_dt - start_dt
    total_minutes = int(duration.total_seconds() // 60)
    
    cursor.execute("""
        UPDATE pontaje 
        SET stop_time = ?, total_minutes = ?
        WHERE id = ?
    """, (end_str, total_minutes, pontaj_id))
    
    conn.commit()
    conn.close()
    return total_minutes

def cancel_active_pontaj(user_id: int) -> bool:
    """Șterge complet pontajul activ al unui user (fără salvare de ore)."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM pontaje WHERE user_id = ? AND stop_time IS NULL", (user_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted

def get_total_pontaje_per_user():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT username, SUM(total_minutes) as total_min, COUNT(id) as nr_pontaje
        FROM pontaje 
        WHERE total_minutes IS NOT NULL
        GROUP BY user_id
        ORDER BY total_min DESC
    """)
    records = cursor.fetchall()
    conn.close()
    return records

def get_user_total_pontaj(user_id: int):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT SUM(total_minutes), COUNT(id)
        FROM pontaje 
        WHERE user_id = ? AND total_minutes IS NOT NULL
    """, (user_id,))
    record = cursor.fetchone()
    conn.close()
    return record if record else (0, 0)

def reset_all_pontaje():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM pontaje")
    conn.commit()
    conn.close()
    print("🧹 Toate pontajele au fost șterse din baza de date.")

if __name__ == "__main__":
    init_db()