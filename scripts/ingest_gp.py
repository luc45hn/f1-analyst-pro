#!/usr/bin/env python3
"""
Script para pre-ingestar datos de un GP desde local a Supabase.
Uso: python scripts/ingest_gp.py 'Hungarian Grand Prix'
     python scripts/ingest_gp.py 'Hungarian Grand Prix' 2026
"""
import sys
import time
from pathlib import Path

# Agregar el directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.weekend_detector import ensure_sessions_loaded
from core.database_manager import F1Database

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

    elapsed = time.time() - start
    print(f"Ingesta completa en {elapsed:.1f}s")

if __name__ == '__main__':
    main()
