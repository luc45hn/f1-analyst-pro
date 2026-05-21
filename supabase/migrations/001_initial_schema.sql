-- F1 Analyst Pro — initial schema for Supabase / PostgreSQL

CREATE TABLE IF NOT EXISTS sessions (
    id          SERIAL PRIMARY KEY,
    year        INTEGER NOT NULL,
    event_name  TEXT    NOT NULL,
    type        TEXT    NOT NULL,
    UNIQUE (year, event_name, type)
);

CREATE TABLE IF NOT EXISTS laps (
    session_id   INTEGER      NOT NULL,
    driver       TEXT         NOT NULL,
    lap_number   INTEGER      NOT NULL,
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
    session_type TEXT         NOT NULL,
    PRIMARY KEY (session_id, driver, lap_number),
    FOREIGN KEY (session_id) REFERENCES sessions (id)
);

CREATE TABLE IF NOT EXISTS weather (
    session_id  INTEGER PRIMARY KEY,
    air_temp    REAL,
    track_temp  REAL,
    humidity    REAL,
    FOREIGN KEY (session_id) REFERENCES sessions (id)
);

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
);

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
);
