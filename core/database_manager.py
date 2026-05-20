
import sqlite3
import pandas as pd
from core.config import DB_PATH

class F1Database:
    def __init__(self, db_path=str(DB_PATH)):
        self.db_path = db_path
        self._create_tables()

    def _create_tables(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    year INTEGER NOT NULL,
                    event_name TEXT NOT NULL,
                    type TEXT NOT NULL,
                    UNIQUE(year, event_name, type)
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS laps (
                    session_id INTEGER,
                    driver TEXT NOT NULL,
                    lap_number INTEGER NOT NULL,
                    lap_time REAL,
                    s1 REAL,
                    s2 REAL,
                    s3 REAL,
                    compound TEXT,
                    tyre_life REAL,
                    stint INTEGER,
                    is_pit_in BOOLEAN,
                    is_pit_out BOOLEAN,
                    track_status TEXT,
                    session_type TEXT NOT NULL,
                    PRIMARY KEY (session_id, driver, lap_number),
                    FOREIGN KEY (session_id) REFERENCES sessions(id)
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS weather (
                    session_id INTEGER PRIMARY KEY,
                    air_temp REAL,
                    track_temp REAL,
                    humidity REAL,
                    FOREIGN KEY (session_id) REFERENCES sessions(id)
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS results (
                    session_id INTEGER,
                    position INTEGER,
                    driver TEXT,
                    team TEXT,
                    time TEXT,
                    points REAL,
                    status TEXT,
                    PRIMARY KEY (session_id, position),
                    FOREIGN KEY (session_id) REFERENCES sessions(id)
                )
            """)
            conn.commit()
            # Migración: agregar stint si la tabla laps ya existía sin esa columna
            cursor.execute("PRAGMA table_info(laps)")
            existing_cols = {row[1] for row in cursor.fetchall()}
            if "stint" not in existing_cols:
                cursor.execute("ALTER TABLE laps ADD COLUMN stint INTEGER")
                conn.commit()
            if "track_status" not in existing_cols:
                cursor.execute("ALTER TABLE laps ADD COLUMN track_status TEXT")
                conn.commit()
            cursor.execute("PRAGMA table_info(results)")
            results_cols = {row[1] for row in cursor.fetchall()}
            if "status" not in results_cols:
                cursor.execute("ALTER TABLE results ADD COLUMN status TEXT")
                conn.commit()
            # Also create a table for qualification results (Q1, Q2, Q3)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS qualy_results (
                    session_id INTEGER,
                    position INTEGER,
                    driver TEXT,
                    team TEXT,
                    q1 TEXT,
                    q2 TEXT,
                    q3 TEXT,
                    PRIMARY KEY (session_id, position),
                    FOREIGN KEY (session_id) REFERENCES sessions(id)
                )
            """)
            conn.commit()

    def get_session_id(self, year, event_name, session_type):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id FROM sessions WHERE year = ? AND event_name = ? AND type = ?",
                (year, event_name, session_type)
            )
            result = cursor.fetchone()
            return result[0] if result else None

    def insert_session(self, year, event_name, session_type):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR IGNORE INTO sessions (year, event_name, type) VALUES (?, ?, ?)",
                (year, event_name, session_type)
            )
            conn.commit()
            return self.get_session_id(year, event_name, session_type)

    def insert_laps_data(self, session_id, laps_df):
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM laps WHERE session_id = ?", (session_id,))
                laps_df["session_id"] = session_id
                laps_df.to_sql("laps", conn, if_exists="append", index=False)
                conn.commit()
        except sqlite3.Error as e:
            raise RuntimeError(f"Error al guardar vueltas (session_id={session_id}): {e}") from e

    def insert_results_data(self, session_id, results_df):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM results WHERE session_id = ?", (session_id,))
            
            results_to_insert = results_df.rename(columns={
                "Position": "position",
                "Abbreviation": "driver",
                "TeamName": "team",
                "Time": "time",
                "Points": "points",
                "Status": "status",
            })
            # Convert timedelta objects to string for database storage
            if "time" in results_to_insert.columns:
                results_to_insert["time"] = results_to_insert["time"].apply(lambda x: str(x) if pd.notna(x) else None)

            # Ensure only columns defined in the schema are inserted and handle potential missing columns gracefully
            required_columns = ["position", "driver", "team", "time", "points", "status"]
            for col in required_columns:
                if col not in results_to_insert.columns:
                    if col in ["driver", "team", "time", "status"]:
                        results_to_insert[col] = None
                    else:
                        results_to_insert[col] = None 
            results_to_insert = results_to_insert[required_columns]
            
            results_to_insert["session_id"] = session_id
            try:
                results_to_insert.to_sql("results", conn, if_exists="append", index=False)
                conn.commit()
            except sqlite3.Error as e:
                raise RuntimeError(f"Error al guardar resultados (session_id={session_id}): {e}") from e

    def insert_qualy_results_data(self, session_id, qualy_results_df):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM qualy_results WHERE session_id = ?", (session_id,))
            
            qualy_to_insert = qualy_results_df.rename(columns={
                "Position": "position",
                "Abbreviation": "driver",
                "TeamName": "team",
                "Q1": "q1",
                "Q2": "q2",
                "Q3": "q3"
            })
            for col in ["q1", "q2", "q3"]:
                if col in qualy_to_insert.columns:
                    qualy_to_insert[col] = qualy_to_insert[col].apply(
                        lambda x: x.total_seconds() if pd.notna(x) and hasattr(x, "total_seconds") else None
                    )
            required_columns = ["position", "driver", "team", "q1", "q2", "q3"]
            for col in required_columns:
                if col not in qualy_to_insert.columns:
                    if col in ["driver", "team"]:
                        qualy_to_insert[col] = ""
                    else:
                        qualy_to_insert[col] = None
            qualy_to_insert = qualy_to_insert[required_columns]

            qualy_to_insert["session_id"] = session_id
            qualy_to_insert.to_sql("qualy_results", conn, if_exists="append", index=False)
            conn.commit()

    def insert_weather_data(self, session_id, weather_data):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR IGNORE INTO weather (session_id, air_temp, track_temp, humidity) VALUES (?, ?, ? ,?)",
                (session_id, weather_data['AirTemp'], weather_data['TrackTemp'], weather_data['Humidity'])
            )
            conn.commit()

    def get_laps_data(self, session_id):
        with sqlite3.connect(self.db_path) as conn:
            return pd.read_sql_query(f"SELECT * FROM laps WHERE session_id = {session_id}", conn)

    def get_results_data(self, session_id):
        with sqlite3.connect(self.db_path) as conn:
            return pd.read_sql_query(f"SELECT * FROM results WHERE session_id = {session_id} ORDER BY position ASC", conn)

    def get_qualy_results_data(self, session_id):
        with sqlite3.connect(self.db_path) as conn:
            return pd.read_sql_query(f"SELECT * FROM qualy_results WHERE session_id = {session_id} ORDER BY position ASC", conn)

    def get_team_lineups(self, session_id) -> dict[str, list[str]]:
        with sqlite3.connect(self.db_path) as conn:
            df = pd.read_sql_query(
                "SELECT team, driver FROM results WHERE session_id = ? ORDER BY position ASC",
                conn, params=(session_id,)
            )
        lineups: dict[str, list[str]] = {}
        for _, row in df.iterrows():
            if row["team"] and row["driver"]:
                lineups.setdefault(row["team"], []).append(row["driver"])
        return lineups

    def get_best_lap_per_driver(self, session_id):
        with sqlite3.connect(self.db_path) as conn:
            return pd.read_sql_query(
                """SELECT l.driver, l.lap_number, l.lap_time, l.s1, l.s2, l.s3,
                          l.compound, l.tyre_life, l.stint, l.is_pit_in, l.is_pit_out, l.track_status
                   FROM laps l
                   JOIN (
                       SELECT driver, MIN(lap_time) AS min_lap
                       FROM laps WHERE session_id = ? AND lap_time IS NOT NULL
                       GROUP BY driver
                   ) agg ON l.driver = agg.driver AND l.lap_time = agg.min_lap
                   WHERE l.session_id = ?
                   ORDER BY l.lap_time ASC""",
                conn, params=(session_id, session_id)
            )

    def get_stint_summary(self, session_id):
        with sqlite3.connect(self.db_path) as conn:
            return pd.read_sql_query(
                """SELECT driver, compound, stint,
                          COUNT(*)                                              AS total_laps,
                          MIN(lap_time)                                         AS best_lap,
                          AVG(CASE WHEN track_status = '1' THEN lap_time END)  AS avg_pace,
                          MIN(tyre_life)                                        AS tyre_life_start,
                          MAX(tyre_life)                                        AS tyre_life_end,
                          MAX(CASE WHEN track_status IS NOT NULL
                                    AND track_status != '1' THEN 1 ELSE 0
                               END)                                             AS has_sc
                   FROM laps
                   WHERE session_id = ? AND lap_time IS NOT NULL
                   GROUP BY driver, compound, stint
                   ORDER BY driver, stint ASC""",
                conn, params=(session_id,)
            )

    def get_top_laps_per_driver(self, session_id, limit=10):
        with sqlite3.connect(self.db_path) as conn:
            return pd.read_sql_query(
                """SELECT driver, lap_number, lap_time, s1, s2, s3,
                          compound, tyre_life, stint, is_pit_in, is_pit_out, track_status
                   FROM (
                       SELECT *,
                              ROW_NUMBER() OVER (PARTITION BY driver ORDER BY lap_time ASC) AS rn
                       FROM laps
                       WHERE session_id = ? AND lap_time IS NOT NULL
                   )
                   WHERE rn <= ?
                   ORDER BY driver, lap_time ASC""",
                conn, params=(session_id, limit)
            )

    def get_top_laps(self, session_id, limit=10):
        with sqlite3.connect(self.db_path) as conn:
            return pd.read_sql_query(
                """SELECT driver, lap_number, lap_time, s1, s2, s3,
                          compound, tyre_life, stint, is_pit_in, is_pit_out, track_status
                   FROM laps
                   WHERE session_id = ? AND lap_time IS NOT NULL
                   ORDER BY lap_time ASC
                   LIMIT ?""",
                conn, params=(session_id, limit)
            )

    def session_exists(self, year, event_name, session_type):
        sid = self.get_session_id(year, event_name, session_type)
        if sid is None:
            return False
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM laps WHERE session_id = ?", (sid,))
            return cursor.fetchone()[0] > 0

    def get_all_sessions(self):
        with sqlite3.connect(self.db_path) as conn:
            return pd.read_sql_query("SELECT * FROM sessions", conn)
