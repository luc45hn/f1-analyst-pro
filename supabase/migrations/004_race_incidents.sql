CREATE TABLE IF NOT EXISTS race_incidents (
    id          SERIAL PRIMARY KEY,
    session_id  INTEGER REFERENCES sessions(id),
    driver      TEXT,
    car_number  TEXT,
    message     TEXT,
    category    TEXT,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (session_id, message)
);
ALTER TABLE race_incidents ENABLE ROW LEVEL SECURITY;
CREATE POLICY "auth_full_access" ON race_incidents
    FOR ALL TO authenticated USING (true) WITH CHECK (true);
