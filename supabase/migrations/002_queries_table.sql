CREATE TABLE queries (
    id              SERIAL PRIMARY KEY,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    user_email      TEXT,
    gp_name         TEXT,
    year            INTEGER,
    prompt          TEXT,
    intent          JSONB,
    has_chart       BOOLEAN,
    input_tokens    INTEGER,
    output_tokens   INTEGER,
    cost_usd        NUMERIC(8,4),
    elapsed_seconds NUMERIC(6,2)
);

ALTER TABLE queries ENABLE ROW LEVEL SECURITY;

CREATE POLICY "auth_full_access" ON queries
    FOR ALL TO authenticated
    USING (true) WITH CHECK (true);
