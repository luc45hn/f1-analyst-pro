import pytest
from unittest.mock import MagicMock
import core.driver_resolver as dr


@pytest.fixture(autouse=True)
def clear_driver_cache():
    dr._driver_cache.clear()
    yield
    dr._driver_cache.clear()


def _make_session():
    session = MagicMock()
    session.drivers = ["COL"]
    session.get_driver.return_value = {
        "Abbreviation": "COL",
        "FirstName": "Franco",
        "LastName": "Colapinto",
    }
    return session


def test_resolves_lastname(mocker):
    mocker.patch("fastf1.get_session", return_value=_make_session())
    mocker.patch("fastf1.Cache.enable_cache")
    mapping = dr.get_driver_name_to_code("Miami Grand Prix", 2026)
    assert mapping["colapinto"] == "COL"


def test_resolves_firstname(mocker):
    mocker.patch("fastf1.get_session", return_value=_make_session())
    mocker.patch("fastf1.Cache.enable_cache")
    mapping = dr.get_driver_name_to_code("Miami Grand Prix", 2026)
    assert mapping["franco"] == "COL"


def test_resolves_abbreviation(mocker):
    mocker.patch("fastf1.get_session", return_value=_make_session())
    mocker.patch("fastf1.Cache.enable_cache")
    mapping = dr.get_driver_name_to_code("Miami Grand Prix", 2026)
    assert mapping["col"] == "COL"


def test_cache_avoids_duplicate_calls(mocker):
    mock_get_session = mocker.patch("fastf1.get_session", return_value=_make_session())
    mocker.patch("fastf1.Cache.enable_cache")
    dr.get_driver_name_to_code("Miami Grand Prix", 2026)
    dr.get_driver_name_to_code("Miami Grand Prix", 2026)
    mock_get_session.assert_called_once()


def test_returns_empty_on_error(mocker):
    mocker.patch("fastf1.get_session", side_effect=Exception("API down"))
    mocker.patch("fastf1.Cache.enable_cache")
    mapping = dr.get_driver_name_to_code("Miami Grand Prix", 2026)
    assert mapping == {}
