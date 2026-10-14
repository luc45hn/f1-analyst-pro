#!/usr/bin/env python3
"""
Script para pre-ingestar datos de un GP desde local a Supabase.
Uso: python scripts/ingest_gp.py 'Hungarian Grand Prix'
     python scripts/ingest_gp.py 'Hungarian Grand Prix' 2026
"""
import os
import sys
import time
from pathlib import Path

# Agregar el directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.weekend_detector import ensure_sessions_loaded
from core.database_manager import F1Database, F1TelemetryDatabase
from core.config import TELEMETRY_DB_URL, SUPABASE_DB_URL

_TELEMETRY_MAX_GB = float(os.getenv("TELEMETRY_MAX_GB", "1"))


def _telemetry_sliding_window():
    """Verificar storage de la DB de telemetría y borrar el GP más antiguo si supera el 75%."""
    import psycopg2
    tel_url = (TELEMETRY_DB_URL or SUPABASE_DB_URL).replace("postgres://", "postgresql://", 1)
    conn = psycopg2.connect(tel_url)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT pg_database_size(current_database())")
            size_bytes = cur.fetchone()[0]
            max_bytes  = _TELEMETRY_MAX_GB * 1024 ** 3
            pct        = size_bytes / max_bytes * 100
            print(f"telemetry | storage: {pct:.1f}% used "
                  f"({size_bytes / 1024**3:.2f} GB / {_TELEMETRY_MAX_GB:.1f} GB)")

            if pct > 75:
                cur.execute(
                    "SELECT DISTINCT session_id FROM telemetry ORDER BY session_id ASC LIMIT 1"
                )
                row = cur.fetchone()
                if row:
                    oldest_id = row[0]
                    gp_label = f"session_id={oldest_id}"
                    try:
                        main_url = SUPABASE_DB_URL.replace("postgres://", "postgresql://", 1)
                        main_conn = psycopg2.connect(main_url)
                        try:
                            with main_conn.cursor() as mcur:
                                mcur.execute(
                                    "SELECT year, event_name, type FROM sessions WHERE id = %s",
                                    (oldest_id,),
                                )
                                srow = mcur.fetchone()
                                if srow:
                                    gp_label = f"{srow[0]} {srow[1]} {srow[2]}"
                        finally:
                            main_conn.close()
                    except Exception as _e:
                        print(f"telemetry | sliding window | could not lookup GP name: {_e}")
                    print(f"telemetry | sliding window | removed oldest GP: {gp_label}")
                    cur.execute("DELETE FROM telemetry WHERE session_id = %s", (oldest_id,))
                    print("telemetry | sliding window | vacuuming...")
                    cur.execute("VACUUM telemetry")
                    print("telemetry | sliding window | done")
    finally:
        conn.close()


def main():
    if len(sys.argv) < 2:
        print("Uso: python scripts/ingest_gp.py 'Nombre del GP' [año]")
        print("Ejemplo: python scripts/ingest_gp.py 'Hungarian Grand Prix' 2026")
        sys.exit(1)

    gp_name = sys.argv[1]
    year = int(sys.argv[2]) if len(sys.argv) > 2 else 2026

    print(f"Ingestando {gp_name} {year}...")
    start = time.time()

    db = F1Database()
    ensure_sessions_loaded(gp_name, db, year)

    _telemetry_sliding_window()

    elapsed = time.time() - start
    print(f"Ingesta completa en {elapsed:.1f}s")

if __name__ == '__main__':
    main()
