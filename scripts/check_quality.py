# Utilidad de exploración — valida que existan vueltas de clasificación con sectores en la DB.
import sqlite3
import pandas as pd

conn = sqlite3.connect('data/f1_analyst.db')
# Buscamos si hay vueltas de Qualy que tengan sectores reales (no nulos ni cero)
query = "SELECT session_type, driver, lap_number, s1, s2, s3 FROM laps WHERE session_type = 'Q' AND s1 > 0 LIMIT 5;"
df = pd.read_sql_query(query, conn)

if df.empty:
    print("❌ ERROR: La base de datos sigue sin tener vueltas de Qualy válidas.")
else:
    print("✅ ÉXITO: Se encontraron vueltas de Qualy con telemetría:")
    print(df)
conn.close()