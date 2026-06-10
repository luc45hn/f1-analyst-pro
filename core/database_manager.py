
import json
import psycopg2
from sqlalchemy import create_engine, text
import pandas as pd
from core.config import SUPABASE_DB_URL
from core.logger import get_logger

_log = get_logger(__name__)


class F1Database:
    def __init__(self):
        self.db_url = SUPABASE_DB_URL
        self._engine = create_engine(
            self.db_url,
            pool_pre_ping=True,
            pool_recycle=300,
            connect_args={"connect_timeout": 10},
        )
        self._create_tables()

    def _connect(self):
        return psycopg2.connect(self.db_url)

    def _create_tables(self):
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS sessions (
                        id          SERIAL PRIMARY KEY,
                        year        INTEGER NOT NULL,
                        event_name  TEXT    NOT NULL,
                        type        TEXT    NOT NULL,
                        UNIQUE (year, event_name, type)
                    )
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS laps (
                        session_id   INTEGER  NOT NULL,
                        driver       TEXT     NOT NULL,
                        lap_number   INTEGER  NOT NULL,
                        lap_time     REAL,
                        s1           REAL,
                        s2           REAL,
                        s3           REAL,
                        compound     TEXT,
                        tyre_life    REAL,
                        stint        INTEGER,
                        is_pit_in    BOOLEAN,
                        is_pit_out   BOOLEAN,
                        track_status TEXT,
                        session_type TEXT     NOT NULL,
                        PRIMARY KEY (session_id, driver, lap_number),
                        FOREIGN KEY (session_id) REFERENCES sessions (id)
                    )
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS weather (
                        session_id  INTEGER PRIMARY KEY,
                        air_temp    REAL,
                        track_temp  REAL,
                        humidity    REAL,
                        FOREIGN KEY (session_id) REFERENCES sessions (id)
                    )
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS results (
                        session_id  INTEGER,
                        position    INTEGER,
                        driver      TEXT,
                        team        TEXT,
                        time        TEXT,
                        points      REAL,
                        status      TEXT,
                        PRIMARY KEY (session_id, position),
                        FOREIGN KEY (session_id) REFERENCES sessions (id)
                    )
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS qualy_results (
                        session_id  INTEGER,
                        position    INTEGER,
                        driver      TEXT,
                        team        TEXT,
                        q1          REAL,
                        q2          REAL,
                        q3          REAL,
                        PRIMARY KEY (session_id, position),
                        FOREIGN KEY (session_id) REFERENCES sessions (id)
                    )
                """)
                # Column migrations for pre-existing databases
                cur.execute("""
                    SELECT column_name FROM information_schema.columns
                    WHERE table_name = 'laps' AND table_schema = 'public'
                """)
                laps_cols = {row[0] for row in cur.fetchall()}
                if "stint" not in laps_cols:
                    cur.execute("ALTER TABLE laps ADD COLUMN stint INTEGER")
                if "track_status" not in laps_cols:
                    cur.execute("ALTER TABLE laps ADD COLUMN track_status TEXT")

                cur.execute("""
                    SELECT column_name FROM information_schema.columns
                    WHERE table_name = 'results' AND table_schema = 'public'
                """)
                results_cols = {row[0] for row in cur.fetchall()}
                if "status" not in results_cols:
                    cur.execute("ALTER TABLE results ADD COLUMN status TEXT")
            conn.commit()
        finally:
            conn.close()

    def get_session_id(self, year, event_name, session_type):
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id FROM sessions WHERE year = %s AND event_name = %s AND type = %s",
                    (year, event_name, session_type),
                )
                result = cur.fetchone()
                return result[0] if result else None
        finally:
            conn.close()

    def insert_session(self, year, event_name, session_type):
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO sessions (year, event_name, type) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
                    (year, event_name, session_type),
                )
            conn.commit()
        finally:
            conn.close()
        return self.get_session_id(year, event_name, session_type)

    def insert_laps_data(self, session_id, laps_df):
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM laps WHERE session_id = %s", (session_id,))
            conn.commit()
        finally:
            conn.close()
        try:
            laps_df["session_id"] = session_id
            laps_df.to_sql("laps", self._engine, if_exists="append", index=False)
        except Exception as e:
            raise RuntimeError(f"Error al guardar vueltas (session_id={session_id}): {e}") from e

    def insert_results_data(self, session_id, results_df):
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM results WHERE session_id = %s", (session_id,))
            conn.commit()
        finally:
            conn.close()

        results_to_insert = results_df.rename(columns={
            "Position": "position",
            "Abbreviation": "driver",
            "TeamName": "team",
            "Time": "time",
            "Points": "points",
            "Status": "status",
        })
        if "time" in results_to_insert.columns:
            results_to_insert["time"] = results_to_insert["time"].apply(
                lambda x: str(x) if pd.notna(x) else None
            )
        required_columns = ["position", "driver", "team", "time", "points", "status"]
        for col in required_columns:
            if col not in results_to_insert.columns:
                results_to_insert[col] = None
        results_to_insert = results_to_insert[required_columns]
        results_to_insert["session_id"] = session_id
        try:
            results_to_insert.to_sql("results", self._engine, if_exists="append", index=False)
        except Exception as e:
            raise RuntimeError(f"Error al guardar resultados (session_id={session_id}): {e}") from e

    def insert_qualy_results_data(self, session_id, qualy_results_df):
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM qualy_results WHERE session_id = %s", (session_id,))
            conn.commit()
        finally:
            conn.close()

        qualy_to_insert = qualy_results_df.rename(columns={
            "Position": "position",
            "Abbreviation": "driver",
            "TeamName": "team",
            "Q1": "q1",
            "Q2": "q2",
            "Q3": "q3",
        })
        for col in ["q1", "q2", "q3"]:
            if col in qualy_to_insert.columns:
                qualy_to_insert[col] = qualy_to_insert[col].apply(
                    lambda x: x.total_seconds() if pd.notna(x) and hasattr(x, "total_seconds") else None
                )
        required_columns = ["position", "driver", "team", "q1", "q2", "q3"]
        for col in required_columns:
            if col not in qualy_to_insert.columns:
                qualy_to_insert[col] = "" if col in ["driver", "team"] else None
        qualy_to_insert = qualy_to_insert[required_columns]
        qualy_to_insert["session_id"] = session_id
        qualy_to_insert.to_sql("qualy_results", self._engine, if_exists="append", index=False)

    def insert_weather_data(self, session_id, weather_data):
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO weather (session_id, air_temp, track_temp, humidity) VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING",
                    (session_id, weather_data["AirTemp"], weather_data["TrackTemp"], weather_data["Humidity"]),
                )
            conn.commit()
        finally:
            conn.close()

    def get_laps_data(self, session_id):
        return pd.read_sql_query(
            text("SELECT * FROM laps WHERE session_id = :sid"),
            self._engine, params={"sid": session_id},
        )

    def get_results_data(self, session_id):
        return pd.read_sql_query(
            text("SELECT * FROM results WHERE session_id = :sid ORDER BY position ASC"),
            self._engine, params={"sid": session_id},
        )

    def get_qualy_results_data(self, session_id):
        return pd.read_sql_query(
            text("SELECT * FROM qualy_results WHERE session_id = :sid ORDER BY position ASC"),
            self._engine, params={"sid": session_id},
        )

    def get_team_lineups(self, session_id) -> dict[str, list[str]]:
        df = pd.read_sql_query(
            text("SELECT team, driver FROM results WHERE session_id = :sid ORDER BY position ASC"),
            self._engine, params={"sid": session_id},
        )
        lineups: dict[str, list[str]] = {}
        for _, row in df.iterrows():
            if row["team"] and row["driver"]:
                lineups.setdefault(row["team"], []).append(row["driver"])
        return lineups

    def get_best_lap_per_driver(self, session_id):
        return pd.read_sql_query(
            text("""SELECT l.driver, l.lap_number, l.lap_time, l.s1, l.s2, l.s3,
                          l.compound, l.tyre_life, l.stint, l.is_pit_in, l.is_pit_out, l.track_status
                   FROM laps l
                   JOIN (
                       SELECT driver, MIN(lap_time) AS min_lap
                       FROM laps WHERE session_id = :sid AND lap_time IS NOT NULL
                       GROUP BY driver
                   ) agg ON l.driver = agg.driver AND l.lap_time = agg.min_lap
                   WHERE l.session_id = :sid
                   ORDER BY l.lap_time ASC"""),
            self._engine, params={"sid": session_id},
        )

    def get_stint_summary(self, session_id):
        return pd.read_sql_query(
            text("""SELECT driver, compound, stint,
                          COUNT(*)                                              AS total_laps,
                          MIN(lap_time)                                         AS best_lap,
                          AVG(CASE WHEN track_status = '1' THEN lap_time END)  AS avg_pace,
                          MIN(tyre_life)                                        AS tyre_life_start,
                          MAX(tyre_life)                                        AS tyre_life_end,
                          MAX(CASE WHEN track_status IS NOT NULL
                                    AND track_status != '1' THEN 1 ELSE 0
                               END)                                             AS has_sc
                   FROM laps
                   WHERE session_id = :sid AND lap_time IS NOT NULL
                   GROUP BY driver, compound, stint
                   ORDER BY driver, stint ASC"""),
            self._engine, params={"sid": session_id},
        )

    def get_top_laps_per_driver(self, session_id, limit=10):
        return pd.read_sql_query(
            text("""SELECT driver, lap_number, lap_time, s1, s2, s3,
                          compound, tyre_life, stint, is_pit_in, is_pit_out, track_status
                   FROM (
                       SELECT *,
                              ROW_NUMBER() OVER (PARTITION BY driver ORDER BY lap_time ASC) AS rn
                       FROM laps
                       WHERE session_id = :sid AND lap_time IS NOT NULL
                   ) sub
                   WHERE rn <= :lim
                   ORDER BY driver, lap_time ASC"""),
            self._engine, params={"sid": session_id, "lim": limit},
        )

    def get_top_laps(self, session_id, limit=10):
        return pd.read_sql_query(
            text("""SELECT driver, lap_number, lap_time, s1, s2, s3,
                          compound, tyre_life, stint, is_pit_in, is_pit_out, track_status
                   FROM laps
                   WHERE session_id = :sid AND lap_time IS NOT NULL
                   ORDER BY lap_time ASC
                   LIMIT :lim"""),
            self._engine, params={"sid": session_id, "lim": limit},
        )

    def session_exists(self, year, event_name, session_type):
        sid = self.get_session_id(year, event_name, session_type)
        if sid is None:
            return False
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM laps WHERE session_id = %s", (sid,))
                return cur.fetchone()[0] > 0
        finally:
            conn.close()

    def get_all_sessions(self):
        return pd.read_sql_query(text("SELECT * FROM sessions"), self._engine)

    def get_pit_stop_analysis(
        self,
        session_id: int,
        position_window: int = 3,
        lap_window: int = 5,
    ) -> pd.DataFrame:
        _COLS = [
            "driver", "pit_lap", "compound_out", "compound_in",
            "position_before", "rival", "rival_pit_lap", "stop_order",
            "position_after", "rival_position_after", "delta_vs_rival", "verdict",
        ]
        laps = pd.read_sql_query(
            text(
                "SELECT driver, lap_number, position, compound, is_pit_in "
                "FROM laps WHERE session_id = :sid ORDER BY driver, lap_number"
            ),
            self._engine,
            params={"sid": session_id},
        )
        if laps.empty or laps["position"].isna().all():
            return pd.DataFrame(columns=_COLS)

        def _pos(driver: str, lap: int):
            d_laps = laps[(laps["driver"] == driver) & laps["position"].notna()]
            if d_laps.empty:
                return None
            exact = d_laps[d_laps["lap_number"] == lap]
            if not exact.empty:
                return int(exact.iloc[0]["position"])
            idx = (d_laps["lap_number"] - lap).abs().idxmin()
            return int(d_laps.loc[idx, "position"])

        def _compound(driver: str, lap: int):
            row = laps[(laps["driver"] == driver) & (laps["lap_number"] == lap)]
            return row.iloc[0]["compound"] if not row.empty else None

        pit_stops = laps[laps["is_pit_in"] == True].copy()
        max_lap = int(laps["lap_number"].max())
        rows = []

        for _, stop in pit_stops.iterrows():
            driver      = stop["driver"]
            pit_lap     = int(stop["lap_number"])
            pos_before  = _pos(driver, pit_lap)
            if pos_before is None:
                continue

            compound_out = stop["compound"]
            compound_in  = _compound(driver, pit_lap + 1)
            best: dict | None = None

            rival_stops = pit_stops[pit_stops["driver"] != driver]
            for _, rstop in rival_stops.iterrows():
                rival          = rstop["driver"]
                rival_pit_lap  = int(rstop["lap_number"])
                if abs(rival_pit_lap - pit_lap) > lap_window:
                    continue
                rival_pos_at_pit = _pos(rival, pit_lap)
                if rival_pos_at_pit is None:
                    continue
                if abs(rival_pos_at_pit - pos_before) > position_window:
                    continue

                check_lap = max(pit_lap, rival_pit_lap) + 3
                if check_lap > max_lap:
                    continue
                pos_after       = _pos(driver, check_lap)
                rival_pos_after = _pos(rival, check_lap)
                if pos_after is None or rival_pos_after is None:
                    continue

                delta = rival_pos_after - pos_after  # positive = gained on rival

                if pit_lap < rival_pit_lap:
                    stop_order = "FIRST"
                    verdict    = "UNDERCUT EXITOSO" if pos_after < rival_pos_after else "UNDERCUT FALLIDO"
                elif pit_lap > rival_pit_lap:
                    stop_order = "SECOND"
                    verdict    = "OVERCUT EXITOSO" if pos_after < rival_pos_after else "OVERCUT FALLIDO"
                else:
                    stop_order = "SAME"
                    verdict    = "PARADA NEUTRAL"

                if best is None or abs(delta) > abs(best["delta_vs_rival"]):
                    best = {
                        "driver": driver, "pit_lap": pit_lap,
                        "compound_out": compound_out, "compound_in": compound_in,
                        "position_before": pos_before, "rival": rival,
                        "rival_pit_lap": rival_pit_lap, "stop_order": stop_order,
                        "position_after": pos_after, "rival_position_after": rival_pos_after,
                        "delta_vs_rival": delta, "verdict": verdict,
                    }

            if best is not None:
                rows.append(best)
            else:
                rows.append({
                    "driver": driver, "pit_lap": pit_lap,
                    "compound_out": compound_out, "compound_in": compound_in,
                    "position_before": pos_before, "rival": None,
                    "rival_pit_lap": None, "stop_order": None,
                    "position_after": _pos(driver, pit_lap + 3) if pit_lap + 3 <= max_lap else None,
                    "rival_position_after": None, "delta_vs_rival": None,
                    "verdict": "PARADA NEUTRAL",
                })

        return pd.DataFrame(rows, columns=_COLS)

    def get_key_moments(self, session_id: int) -> pd.DataFrame:
        laps = pd.read_sql_query(
            text(
                "SELECT driver, lap_number, lap_time, s1, s2, s3, position, "
                "is_pit_in, is_personal_best, deleted, deleted_reason, track_status "
                "FROM laps WHERE session_id = :sid ORDER BY driver, lap_number"
            ),
            self._engine,
            params={"sid": session_id},
        )
        if laps.empty:
            return pd.DataFrame(columns=["event_type", "driver", "lap_number"])

        parts = []

        # TRACK_LIMITS
        if laps["deleted"].notna().any():
            tl = laps[laps["deleted"] == True][
                ["driver", "lap_number", "deleted_reason", "s1", "s2", "s3"]
            ].copy()
            if not tl.empty:
                tl["event_type"] = "TRACK_LIMITS"
                parts.append(tl)

        # RITMO_ANOMALO: lap_time > mediana_piloto * 1.15, pista verde
        green = laps[(laps["track_status"] == "1") & laps["lap_time"].notna()].copy()
        if not green.empty:
            medians = green.groupby("driver")["lap_time"].median().rename("ritmo_base")
            green = green.join(medians, on="driver")
            anomalas = green[green["lap_time"] > green["ritmo_base"] * 1.15][
                ["driver", "lap_number", "lap_time", "ritmo_base"]
            ].copy()
            if not anomalas.empty:
                anomalas["event_type"] = "RITMO_ANOMALO"
                parts.append(anomalas)

        # PERDIDA_POSICION: sube 3+ puestos sin pit in
        if laps["position"].notna().any():
            pos = laps[laps["position"].notna() & (laps["is_pit_in"] != True)].copy()
            pos = pos.sort_values(["driver", "lap_number"])
            pos["position_before"] = pos.groupby("driver")["position"].shift(1)
            pos = pos[pos["position_before"].notna()].copy()
            pos["delta"] = (pos["position"] - pos["position_before"]).astype(int)
            perdidas = pos[pos["delta"] >= 3][
                ["driver", "lap_number", "position_before", "position", "delta"]
            ].copy()
            perdidas = perdidas.rename(columns={"position": "position_after"})
            perdidas["position_before"] = perdidas["position_before"].astype(int)
            if not perdidas.empty:
                perdidas["event_type"] = "PERDIDA_POSICION"
                parts.append(perdidas)

        # MEJOR_VUELTA: is_personal_best=True, pista verde, top 5 del campo
        if laps["is_personal_best"].notna().any():
            pb = laps[
                (laps["is_personal_best"] == True)
                & (laps["track_status"] == "1")
                & laps["lap_time"].notna()
            ][["driver", "lap_number", "lap_time"]].copy()
            pb = pb.nsmallest(5, "lap_time")
            if not pb.empty:
                pb["event_type"] = "MEJOR_VUELTA"
                parts.append(pb)

        if not parts:
            return pd.DataFrame(columns=["event_type", "driver", "lap_number"])

        return (
            pd.concat(parts, ignore_index=True)
            .sort_values(["lap_number", "event_type"])
            .reset_index(drop=True)
        )

    def log_query(self, user_email, gp_name, year, prompt, intent,
                  has_chart, input_tokens, output_tokens, cost_usd, elapsed_seconds):
        try:
            conn = self._connect()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        """INSERT INTO queries
                           (user_email, gp_name, year, prompt, intent,
                            has_chart, input_tokens, output_tokens, cost_usd, elapsed_seconds)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                        (user_email, gp_name, year, prompt,
                         json.dumps(intent), has_chart,
                         input_tokens, output_tokens, cost_usd, elapsed_seconds),
                    )
                conn.commit()
            finally:
                conn.close()
        except Exception:
            _log.warning("log_query failed silently | gp=%s", gp_name)

    def get_daily_cost(self, user_email: str, date) -> float:
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT COALESCE(SUM(cost_usd), 0)
                       FROM queries
                       WHERE user_email = %s
                       AND DATE(created_at) = %s""",
                    (user_email, date),
                )
                return float(cur.fetchone()[0])
        finally:
            conn.close()
