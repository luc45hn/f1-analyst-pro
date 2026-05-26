import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool
from core.database_manager import F1Database


class _SQLiteF1Database(F1Database):
    """Subclase de test: reemplaza psycopg2 + Supabase con SQLite en memoria."""

    def __init__(self, engine):
        self._engine = engine          # no llama a super().__init__()
        self._create_tables()

    def _connect(self):
        raise NotImplementedError      # nunca se usa en esta subclase

    def _create_tables(self):
        with self._engine.begin() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    year       INTEGER NOT NULL,
                    event_name TEXT    NOT NULL,
                    type       TEXT    NOT NULL,
                    UNIQUE (year, event_name, type)
                )
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS laps (
                    session_id   INTEGER NOT NULL,
                    driver       TEXT    NOT NULL,
                    lap_number   INTEGER NOT NULL,
                    lap_time     REAL,
                    s1 REAL, s2 REAL, s3 REAL,
                    compound     TEXT,
                    tyre_life    REAL,
                    stint        INTEGER,
                    is_pit_in    BOOLEAN,
                    is_pit_out   BOOLEAN,
                    track_status TEXT,
                    session_type TEXT    NOT NULL,
                    PRIMARY KEY (session_id, driver, lap_number),
                    FOREIGN KEY (session_id) REFERENCES sessions (id)
                )
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS results (
                    session_id INTEGER,
                    position   INTEGER,
                    driver     TEXT,
                    team       TEXT,
                    time       TEXT,
                    points     REAL,
                    status     TEXT,
                    PRIMARY KEY (session_id, position),
                    FOREIGN KEY (session_id) REFERENCES sessions (id)
                )
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS qualy_results (
                    session_id INTEGER,
                    position   INTEGER,
                    driver     TEXT,
                    team       TEXT,
                    q1 REAL, q2 REAL, q3 REAL,
                    PRIMARY KEY (session_id, position),
                    FOREIGN KEY (session_id) REFERENCES sessions (id)
                )
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS weather (
                    session_id INTEGER PRIMARY KEY,
                    air_temp   REAL,
                    track_temp REAL,
                    humidity   REAL,
                    FOREIGN KEY (session_id) REFERENCES sessions (id)
                )
            """))

    def get_session_id(self, year, event_name, session_type):
        with self._engine.connect() as conn:
            row = conn.execute(
                text("SELECT id FROM sessions WHERE year = :y AND event_name = :e AND type = :t"),
                {"y": year, "e": event_name, "t": session_type},
            ).fetchone()
            return row[0] if row else None

    def insert_session(self, year, event_name, session_type):
        with self._engine.begin() as conn:
            conn.execute(
                text("INSERT OR IGNORE INTO sessions (year, event_name, type) VALUES (:y, :e, :t)"),
                {"y": year, "e": event_name, "t": session_type},
            )
        return self.get_session_id(year, event_name, session_type)

    def session_exists(self, year, event_name, session_type):
        sid = self.get_session_id(year, event_name, session_type)
        if sid is None:
            return False
        with self._engine.connect() as conn:
            count = conn.execute(
                text("SELECT COUNT(*) FROM laps WHERE session_id = :sid"),
                {"sid": sid},
            ).fetchone()[0]
            return count > 0

    def insert_laps_data(self, session_id, laps_df):
        with self._engine.begin() as conn:
            conn.execute(text("DELETE FROM laps WHERE session_id = :sid"), {"sid": session_id})
        df = laps_df.copy()
        df["session_id"] = session_id
        df.to_sql("laps", self._engine, if_exists="append", index=False)


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    yield _SQLiteF1Database(engine)
    engine.dispose()
