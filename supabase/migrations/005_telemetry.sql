CREATE TABLE IF NOT EXISTS telemetry (
    session_id INTEGER REFERENCES sessions(id),
    driver     TEXT    NOT NULL,
    lap_number INTEGER NOT NULL,
    distance   FLOAT   NOT NULL,
    speed      FLOAT,
    throttle   FLOAT,
    brake      FLOAT,
    gear       INTEGER,
    PRIMARY KEY (session_id, driver, lap_number, distance)
);
ALTER TABLE telemetry ENABLE ROW LEVEL SECURITY;
CREATE POLICY "auth_full_access" ON telemetry
    FOR ALL TO authenticated USING (true) WITH CHECK (true);
