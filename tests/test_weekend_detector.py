import pytest
from unittest.mock import MagicMock
import core.weekend_detector as wd
from core.gp_resolver import GPNotFoundError


@pytest.fixture(autouse=True)
def clear_event_cache():
    """Limpia el cache de módulo antes y después de cada test."""
    wd._event_cache.clear()
    yield
    wd._event_cache.clear()


def _make_event(fmt: str, session_names: list[str], event_name: str = "Miami Grand Prix"):
    event = MagicMock()
    event.__getitem__ = MagicMock(side_effect=lambda key: {
        "EventFormat": fmt,
        "EventName":   event_name,
    }.get(key, fmt))
    event.get_session_name.side_effect = lambda i: session_names[i - 1]
    return event


NORMAL_SESSIONS = ["Practice 1", "Practice 2", "Practice 3", "Qualifying", "Race"]
SPRINT_SESSIONS = ["Practice 1", "Sprint Qualifying", "Sprint", "Qualifying", "Race"]


# ── Tests existentes (mantenidos) ──────────────────────────────────────────────

def test_normal_weekend(mocker):
    mocker.patch("fastf1.get_event", return_value=_make_event("conventional", NORMAL_SESSIONS))
    mocker.patch("fastf1.Cache.enable_cache")
    assert wd.detect_weekend_type("Miami Grand Prix", 2026) == "normal"


def test_sprint_weekend(mocker):
    mocker.patch("fastf1.get_event", return_value=_make_event("sprint", SPRINT_SESSIONS))
    mocker.patch("fastf1.Cache.enable_cache")
    assert wd.detect_weekend_type("Miami Grand Prix", 2026) == "sprint"


def test_fallback_on_error(mocker):
    mocker.patch("fastf1.get_event", side_effect=Exception("API error"))
    mocker.patch("fastf1.Cache.enable_cache")
    assert wd.detect_weekend_type("Miami Grand Prix", 2026) == "normal"


def test_sessions_normal(mocker):
    mocker.patch("fastf1.get_event", return_value=_make_event("conventional", NORMAL_SESSIONS))
    mocker.patch("fastf1.Cache.enable_cache")
    assert wd._get_sessions("Miami Grand Prix", 2026) == ["FP1", "FP2", "FP3", "Q", "R"]


def test_sessions_sprint(mocker):
    mocker.patch("fastf1.get_event", return_value=_make_event("sprint", SPRINT_SESSIONS))
    mocker.patch("fastf1.Cache.enable_cache")
    assert wd._get_sessions("Miami Grand Prix", 2026) == ["FP1", "SQ", "SS", "Q", "R"]


# ── GPNotFoundError ────────────────────────────────────────────────────────────

def test_get_event_raises_gp_not_found_on_value_error(mocker):
    """_get_event convierte ValueError de FastF1 en GPNotFoundError."""
    mocker.patch("fastf1.get_event", side_effect=ValueError("No GP found"))
    mocker.patch("fastf1.Cache.enable_cache")
    with pytest.raises(GPNotFoundError):
        wd._get_event(2026, "xyzzy grand prix")


def test_get_event_raises_gp_not_found_for_empty_event_name(mocker):
    """_get_event lanza GPNotFoundError si EventName viene vacío."""
    event = MagicMock()
    event.__getitem__ = MagicMock(return_value="")   # EventName vacío
    event.get.return_value = ""
    mocker.patch("fastf1.get_event", return_value=event)
    mocker.patch("fastf1.Cache.enable_cache")
    with pytest.raises(GPNotFoundError):
        wd._get_event(2026, "xyzzy")


# ── ensure_sessions_loaded ────────────────────────────────────────────────────

def test_ensure_sessions_loaded_raises_for_invalid_gp(mocker, db):
    """ensure_sessions_loaded re-lanza GPNotFoundError para nombres inválidos."""
    mocker.patch("fastf1.get_event", side_effect=ValueError("No GP found"))
    mocker.patch("fastf1.Cache.enable_cache")
    with pytest.raises(GPNotFoundError):
        wd.ensure_sessions_loaded("xyzzy grand prix", db, year=2026)


def test_ensure_sessions_loaded_uses_official_name(mocker, db):
    """ensure_sessions_loaded usa event['EventName'] para las consultas a DB."""
    official = "Austrian Grand Prix"
    event = _make_event("conventional", NORMAL_SESSIONS, event_name=official)
    mocker.patch("fastf1.get_event", return_value=event)
    mocker.patch("fastf1.Cache.enable_cache")

    # Mockear get_session_data para evitar descarga real
    mocker.patch("core.weekend_detector.get_session_data", return_value=None)

    # Forzar que session_exists use el nombre oficial y no el input raw
    calls = []
    original_exists = db.session_exists
    def tracking_exists(year, name, stype):
        calls.append(name)
        return original_exists(year, name, stype)
    db.session_exists = tracking_exists

    wd.ensure_sessions_loaded("austria", db, year=2026)

    # Todas las consultas a DB usaron el nombre oficial, no "austria"
    assert all(name == official for name in calls), f"Se usaron nombres no oficiales: {calls}"
