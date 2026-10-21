#!/usr/bin/env python3
import os
import sys
import psycopg2

SUPABASE_DB_URL  = os.environ["SUPABASE_DB_URL"]
TELEMETRY_DB_URL = os.environ["TELEMETRY_DB_URL"]

ok = True

try:
    conn = psycopg2.connect(SUPABASE_DB_URL, connect_timeout=10)
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM sessions LIMIT 1")
    conn.close()
    print("keepalive | supabase: OK")
except Exception as e:
    print(f"keepalive | supabase: FAILED — {e}", file=sys.stderr)
    ok = False

try:
    url = TELEMETRY_DB_URL.replace("postgres://", "postgresql://", 1)
    conn = psycopg2.connect(url, connect_timeout=10)
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM telemetry LIMIT 1")
    conn.close()
    print("keepalive | aiven: OK")
except Exception as e:
    print(f"keepalive | aiven: FAILED — {e}", file=sys.stderr)
    ok = False

if not ok:
    sys.exit(1)
