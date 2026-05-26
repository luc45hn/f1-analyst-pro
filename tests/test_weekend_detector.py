import pytest
from unittest.mock import MagicMock
import core.weekend_detector as wd


@pytest.fixture(autouse=True)
def clear_event_cache():
    """Limpia el cache de módulo antes y después de cada test."""
    wd._event_cache.clear()
    yield
    wd._event_cache.clear()


def _make_event(fmt: str, session_names: list[str]):
    event = MagicMock()
    event.__getitem__ = MagicMock(return_value=fmt)
    event.get_session_name.side_effect = lambda i: session_names[i - 1]
    return event


NORMAL_SESSIONS = ["Practice 1", "Practice 2", "Practice 3", "Qualifying", "Race"]
SPRINT_SESSIONS = ["Practice 1", "Sprint Qualifying", "Sprint", "Qualifying", "Race"]


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
