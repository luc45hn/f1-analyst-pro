import pandas as pd
import pytest
from sqlalchemy import text


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_laps(*drivers_laps: tuple) -> pd.DataFrame:
    """
    Construye un DataFrame de laps a partir de tuplas
    (driver, lap_number, lap_time, compound, stint, track_status).
    """
    rows = []
    for drv, ln, lt, compound, stint, ts in drivers_laps:
        rows.append({
            "driver": drv, "lap_number": ln, "lap_time": lt,
            "s1": lt * 0.30, "s2": lt * 0.40, "s3": lt * 0.30,
            "compound": compound, "tyre_life": ln, "stint": stint,
            "is_pit_in": False, "is_pit_out": False,
            "track_status": ts, "session_type": "R",
        })
    return pd.DataFrame(rows)


def _insert_session_with_laps(db, laps_df, gp="Austrian Grand Prix", year=2026, stype="R"):
    sid = db.insert_session(year, gp, stype)
    db.insert_laps_data(sid, laps_df)
    return sid


def _insert_results(db, session_id, rows: list[dict]):
    """Inserta resultados directamente via engine (bypass de insert_results_data
    que requiere psycopg2 para el DELETE)."""
    with db._engine.begin() as conn:
        for r in rows:
            conn.execute(text(
                "INSERT INTO results (session_id, position, driver, team, time, points, status) "
                "VALUES (:sid, :pos, :drv, :team, :time, :pts, :status)"
            ), {"sid": session_id, "pos": r["position"], "drv": r["driver"],
                "team": r["team"], "time": r.get("time"), "pts": r.get("points", 0),
                "status": r.get("status", "Finished")})


# ── Tests existentes (mantenidos) ──────────────────────────────────────────────

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


# ── get_laps_data ──────────────────────────────────────────────────────────────

def test_get_laps_data_returns_correct_count(db):
    """get_laps_data devuelve exactamente los laps insertados para esa sesión."""
    laps = _make_laps(
        ("COL", 1, 82.5, "SOFT", 1, "1"),
        ("COL", 2, 81.2, "SOFT", 1, "1"),
        ("RUS", 1, 83.1, "MEDIUM", 1, "1"),
    )
    sid = _insert_session_with_laps(db, laps)
    result = db.get_laps_data(sid)
    assert len(result) == 3


def test_get_laps_data_empty_for_missing_session(db):
    """get_laps_data devuelve DataFrame vacío si la sesión no tiene laps."""
    result = db.get_laps_data(session_id=9999)
    assert result.empty


def test_get_laps_data_contains_correct_drivers(db):
    laps = _make_laps(
        ("COL", 1, 82.5, "SOFT", 1, "1"),
        ("RUS", 1, 83.1, "MEDIUM", 1, "1"),
    )
    sid = _insert_session_with_laps(db, laps)
    result = db.get_laps_data(sid)
    assert set(result["driver"].unique()) == {"COL", "RUS"}


# ── get_best_lap_per_driver ────────────────────────────────────────────────────

def test_get_best_lap_per_driver_returns_minimum(db):
    """El best lap de COL es 81.2s, no 82.5s."""
    laps = _make_laps(
        ("COL", 1, 82.5, "SOFT", 1, "1"),
        ("COL", 2, 81.2, "SOFT", 1, "1"),
    )
    sid = _insert_session_with_laps(db, laps)
    result = db.get_best_lap_per_driver(sid)
    assert len(result) == 1
    assert result.iloc[0]["lap_time"] == pytest.approx(81.2)


def test_get_best_lap_per_driver_one_row_per_driver(db):
    """Un row por piloto, aunque cada uno tenga varias vueltas."""
    laps = _make_laps(
        ("COL", 1, 82.5, "SOFT", 1, "1"),
        ("COL", 2, 81.2, "SOFT", 1, "1"),
        ("RUS", 1, 83.1, "MEDIUM", 1, "1"),
        ("RUS", 2, 82.0, "MEDIUM", 1, "1"),
    )
    sid = _insert_session_with_laps(db, laps)
    result = db.get_best_lap_per_driver(sid)
    assert len(result) == 2


def test_get_best_lap_per_driver_sorted_ascending(db):
    """El resultado está ordenado por lap_time ascendente."""
    laps = _make_laps(
        ("COL", 1, 81.2, "SOFT", 1, "1"),
        ("RUS", 1, 83.1, "MEDIUM", 1, "1"),
    )
    sid = _insert_session_with_laps(db, laps)
    result = db.get_best_lap_per_driver(sid)
    times = result["lap_time"].tolist()
    assert times == sorted(times)


# ── get_stint_summary ──────────────────────────────────────────────────────────

def test_get_stint_summary_returns_one_row_per_stint(db):
    """Devuelve un row por (driver, compound, stint)."""
    laps = _make_laps(
        ("COL", 1, 82.5, "SOFT",   1, "1"),
        ("COL", 2, 81.2, "SOFT",   1, "1"),
        ("COL", 3, 83.0, "MEDIUM", 2, "1"),  # stint 2
        ("RUS", 1, 83.1, "MEDIUM", 1, "1"),
    )
    sid = _insert_session_with_laps(db, laps)
    result = db.get_stint_summary(sid)
    # COL stint 1 + COL stint 2 + RUS stint 1 = 3 rows
    assert len(result) == 3


def test_get_stint_summary_total_laps_correct(db):
    """total_laps cuenta correctamente las vueltas de cada stint."""
    laps = _make_laps(
        ("COL", 1, 82.5, "SOFT", 1, "1"),
        ("COL", 2, 81.2, "SOFT", 1, "1"),
        ("COL", 3, 82.0, "SOFT", 1, "1"),
    )
    sid = _insert_session_with_laps(db, laps)
    result = db.get_stint_summary(sid)
    assert len(result) == 1
    assert result.iloc[0]["total_laps"] == 3


def test_get_stint_summary_best_lap_correct(db):
    """best_lap es el mínimo de lap_time en el stint."""
    laps = _make_laps(
        ("COL", 1, 82.5, "SOFT", 1, "1"),
        ("COL", 2, 81.2, "SOFT", 1, "1"),
    )
    sid = _insert_session_with_laps(db, laps)
    result = db.get_stint_summary(sid)
    assert result.iloc[0]["best_lap"] == pytest.approx(81.2)


# ── get_top_laps_per_driver / get_top_laps ────────────────────────────────────

def test_get_top_laps_per_driver_respects_limit(db):
    """Con limit=1, devuelve exactamente 1 vuelta por piloto."""
    laps = _make_laps(
        ("COL", 1, 82.5, "SOFT", 1, "1"),
        ("COL", 2, 81.2, "SOFT", 1, "1"),
        ("COL", 3, 83.0, "SOFT", 1, "1"),
        ("RUS", 1, 84.0, "MEDIUM", 1, "1"),
        ("RUS", 2, 83.5, "MEDIUM", 1, "1"),
    )
    sid = _insert_session_with_laps(db, laps)
    result = db.get_top_laps_per_driver(sid, limit=1)
    # 1 vuelta × 2 pilotos = 2 rows
    assert len(result) == 2
    # Las vueltas devueltas son las más rápidas de cada piloto
    col_row = result[result["driver"] == "COL"]
    assert col_row.iloc[0]["lap_time"] == pytest.approx(81.2)


def test_get_top_laps_overall_limit(db):
    """get_top_laps devuelve exactamente N vueltas ordenadas por tiempo."""
    laps = _make_laps(
        ("COL", 1, 82.5, "SOFT", 1, "1"),
        ("COL", 2, 81.2, "SOFT", 1, "1"),
        ("RUS", 1, 83.1, "MEDIUM", 1, "1"),
        ("RUS", 2, 80.9, "MEDIUM", 1, "1"),
    )
    sid = _insert_session_with_laps(db, laps)
    result = db.get_top_laps(sid, limit=2)
    assert len(result) == 2
    # El más rápido es RUS vuelta 2 (80.9s)
    assert result.iloc[0]["lap_time"] == pytest.approx(80.9)


# ── get_team_lineups ───────────────────────────────────────────────────────────

def test_get_team_lineups_with_data(db):
    """get_team_lineups devuelve el dict correcto con datos reales."""
    sid = db.insert_session(2026, "Austrian Grand Prix", "R")
    _insert_results(db, sid, [
        {"position": 1, "driver": "COL", "team": "Alpine"},
        {"position": 2, "driver": "GAS", "team": "Alpine"},
        {"position": 3, "driver": "RUS", "team": "Mercedes"},
    ])
    lineups = db.get_team_lineups(sid)
    assert set(lineups["Alpine"]) == {"COL", "GAS"}
    assert lineups["Mercedes"] == ["RUS"]


def test_get_team_lineups_two_teams(db):
    """El número de teams en lineups es correcto."""
    sid = db.insert_session(2026, "Austrian Grand Prix", "Q")
    _insert_results(db, sid, [
        {"position": 1, "driver": "NOR", "team": "McLaren"},
        {"position": 2, "driver": "PIA", "team": "McLaren"},
        {"position": 3, "driver": "VER", "team": "Red Bull"},
    ])
    lineups = db.get_team_lineups(sid)
    assert len(lineups) == 2
    assert len(lineups["McLaren"]) == 2
