import pandas as pd


def test_session_not_exists(db):
    assert db.session_exists(2026, "Miami Grand Prix", "R") is False


def test_insert_and_get_session(db):
    sid = db.insert_session(2026, "Miami Grand Prix", "R")
    assert sid is not None
    lap = pd.DataFrame([{
        "driver": "COL", "lap_number": 1, "lap_time": 90.5,
        "s1": 30.0, "s2": 30.0, "s3": 30.5,
        "compound": "SOFT", "tyre_life": 1, "stint": 1,
        "is_pit_in": False, "is_pit_out": False,
        "track_status": "1", "session_type": "R",
    }])
    db.insert_laps_data(sid, lap)
    assert db.session_exists(2026, "Miami Grand Prix", "R") is True


def test_get_session_id_returns_none(db):
    assert db.get_session_id(2026, "Miami Grand Prix", "Q") is None


def test_get_team_lineups_empty(db):
    sid = db.insert_session(2026, "Miami Grand Prix", "R")
    assert db.get_team_lineups(sid) == {}


def test_idempotent_insert(db):
    db.insert_session(2026, "Miami Grand Prix", "R")
    db.insert_session(2026, "Miami Grand Prix", "R")
    assert len(db.get_all_sessions()) == 1
