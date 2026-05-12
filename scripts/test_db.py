# Utilidad de exploración — cuenta filas en la tabla laps de la DB.
import sqlite3
import os

DB_PATH = os.getenv("DATABASE_PATH", "data/f1_analyst.db")

try:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM laps")
    count = cursor.fetchone()[0]
    print(f"DEBUG: La tabla laps contiene {count} filas.")
except sqlite3.Error as e:
    print(f"ERROR: Error de base de datos: {e}")
finally:
    if conn:
        conn.close()