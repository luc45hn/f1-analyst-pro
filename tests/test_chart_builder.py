"""Tests para core/chart_builder.py — plot_telemetry_trace.

Estrategia de mock:
- fastf1.get_session y fastf1.Cache.enable_cache se parchean a nivel módulo.
- session.laps se implementa como subclase de pd.DataFrame (_MockLaps)
  cuyos rows devuelven _MockLap (subclase de pd.Series con get_car_data()).
- CACHE_DIR.mkdir se parchea para evitar I/O de filesystem.
"""
import numpy as np
import pandas as pd
import pytest
from unittest.mock import MagicMock, patch
import plotly.graph_objects as go

from core.chart_builder import plot_telemetry_trace


# ── Helpers de mock ────────────────────────────────────────────────────────────

def _make_car_data(n: int = 50, dist_start: float = 0.0, dist_end: float = 1000.0) -> pd.DataFrame:
    """DataFrame de telemetría sintética con n puntos entre dist_start y dist_end."""
    return pd.DataFrame({
        "Distance": np.linspace(dist_start, dist_end, n),
        "Speed":    np.full(n, 200.0),
        "Throttle": np.full(n, 80.0),
        "Brake":    np.zeros(n, dtype=float),
        "nGear":    np.full(n, 6, dtype=int),
    })


class _MockLap(pd.Series):
    """Series con get_car_data(), igual a un FastF1 Lap."""

    @property
    def _constructor(self):
        return _MockLap

    def get_car_data(self):
        mock = MagicMock()
        mock.add_distance.return_value = _make_car_data()
        return mock


class _MockLaps(pd.DataFrame):
    """DataFrame que devuelve _MockLap en operaciones de fila (loc, iloc, iterrows)."""

    @property
    def _constructor(self):
        return _MockLaps

    @property
    def _constructor_sliced(self):
        return _MockLap


def _make_session(driver_laps: dict[str, list[tuple[int, float]]]) -> MagicMock:
    """
    Crea un mock de sesión FastF1 con las vueltas indicadas.

    Args:
        driver_laps: {"COL": [(5, 82.5), (6, 81.2)], "RUS": [(5, 83.1)]}
            Cada tupla es (lap_number, lap_time_en_segundos).
    """
    rows = []
    for drv, laps in driver_laps.items():
        for ln, lt in laps:
            rows.append({
                "Driver":    drv,
                "LapNumber": float(ln),
                "LapTime":   pd.Timedelta(seconds=lt),
                "Stint":     1,
            })

    laps_df = _MockLaps(pd.DataFrame(rows)) if rows else _MockLaps()
    session = MagicMock()
    session.laps = laps_df
    session.name = "Q"
    return session


# ── Fixtures de patch compartidos ─────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _patch_cache_dir(tmp_path):
    """Redirige CACHE_DIR a un directorio temporal para evitar I/O real.
    Se parchea en core.config porque la función lo importa con 'from core.config import CACHE_DIR'.
    """
    with patch("core.config.CACHE_DIR", tmp_path):
        yield


# ── Tests ─────────────────────────────────────────────────────────────────────

@patch("fastf1.Cache.enable_cache")
@patch("fastf1.get_session")
def test_returns_none_on_fastf1_exception(mock_get_session, mock_cache):
    """Si FastF1 lanza excepción al cargar la sesión, retorna None."""
    mock_get_session.side_effect = Exception("API down")
    result = plot_telemetry_trace(None, "Austrian Grand Prix", 2026, ["COL"], "Q")
    assert result is None


@patch("fastf1.Cache.enable_cache")
@patch("fastf1.get_session")
def test_returns_none_when_driver_not_in_session(mock_get_session, mock_cache):
    """Si el piloto no tiene vueltas en la sesión, la figura queda vacía → None."""
    session = _make_session({"RUS": [(1, 82.5)]})
    mock_get_session.return_value = session
    result = plot_telemetry_trace(None, "Austrian Grand Prix", 2026, ["COL"], "Q")
    assert result is None


@patch("fastf1.Cache.enable_cache")
@patch("fastf1.get_session")
def test_returns_figure_normal_mode_one_driver(mock_get_session, mock_cache):
    """Modo normal con un piloto devuelve Figure con 4 trazas (Speed/Throttle/Brake/Gear)."""
    session = _make_session({"COL": [(5, 82.5), (6, 81.2)]})
    mock_get_session.return_value = session
    result = plot_telemetry_trace(None, "Austrian Grand Prix", 2026, ["COL"], "Q")
    assert isinstance(result, go.Figure)
    assert len(result.data) == 4


@patch("fastf1.Cache.enable_cache")
@patch("fastf1.get_session")
def test_returns_figure_normal_mode_two_drivers(mock_get_session, mock_cache):
    """Modo normal con dos pilotos devuelve 8 trazas (4 canales × 2 pilotos)."""
    session = _make_session({"COL": [(5, 82.5)], "RUS": [(5, 83.1)]})
    mock_get_session.return_value = session
    result = plot_telemetry_trace(None, "Austrian Grand Prix", 2026, ["COL", "RUS"], "Q")
    assert isinstance(result, go.Figure)
    assert len(result.data) == 8


@patch("fastf1.Cache.enable_cache")
@patch("fastf1.get_session")
def test_compare_laps_mode_produces_eight_traces(mock_get_session, mock_cache):
    """compare_laps_mode (Q3 + 1 piloto) usa las 2 mejores vueltas → 8 trazas."""
    session = _make_session({"COL": [(5, 82.5), (6, 81.2), (7, 83.0)]})
    mock_get_session.return_value = session
    result = plot_telemetry_trace(
        None, "Austrian Grand Prix", 2026, ["COL"], "Q",
        qualifying_segment="Q3",
    )
    assert isinstance(result, go.Figure)
    assert len(result.data) == 8


@patch("fastf1.Cache.enable_cache")
@patch("fastf1.get_session")
def test_compare_laps_mode_falls_back_when_only_one_valid_lap(mock_get_session, mock_cache):
    """Si solo hay 1 vuelta válida en compare_mode, devuelve Figure con 4 trazas."""
    session = _make_session({"COL": [(5, 82.5)]})
    mock_get_session.return_value = session
    result = plot_telemetry_trace(
        None, "Austrian Grand Prix", 2026, ["COL"], "Q",
        qualifying_segment="Q3",
    )
    assert isinstance(result, go.Figure)
    assert len(result.data) == 4


@patch("fastf1.Cache.enable_cache")
@patch("fastf1.get_session")
def test_explicit_laps_mode_uses_both_specified_laps(mock_get_session, mock_cache):
    """explicit_laps_mode con lap_numbers=[5,6] produce 8 trazas."""
    session = _make_session({"COL": [(5, 82.5), (6, 81.2)]})
    mock_get_session.return_value = session
    result = plot_telemetry_trace(
        None, "Austrian Grand Prix", 2026, ["COL"], "Q",
        lap_numbers=[5, 6],
    )
    assert isinstance(result, go.Figure)
    assert len(result.data) == 8


@patch("fastf1.Cache.enable_cache")
@patch("fastf1.get_session")
def test_explicit_laps_mode_missing_lap_skipped(mock_get_session, mock_cache):
    """Si lap_numbers incluye una vuelta que no existe, se omite (4 trazas, no 8)."""
    session = _make_session({"COL": [(5, 82.5)]})
    mock_get_session.return_value = session
    result = plot_telemetry_trace(
        None, "Austrian Grand Prix", 2026, ["COL"], "Q",
        lap_numbers=[5, 99],   # vuelta 99 no existe
    )
    assert isinstance(result, go.Figure)
    assert len(result.data) == 4


@patch("fastf1.Cache.enable_cache")
@patch("fastf1.get_session")
def test_distance_filter_reduces_data_points(mock_get_session, mock_cache):
    """Con distance_min/max, las trazas tienen menos puntos que sin filtro."""
    session = _make_session({"COL": [(5, 82.5)]})
    mock_get_session.return_value = session

    result_full = plot_telemetry_trace(
        None, "Austrian Grand Prix", 2026, ["COL"], "Q",
    )
    # Nueva sesión mock para el segundo call (evitar estado compartido)
    session2 = _make_session({"COL": [(5, 82.5)]})
    mock_get_session.return_value = session2

    result_zone = plot_telemetry_trace(
        None, "Austrian Grand Prix", 2026, ["COL"], "Q",
        distance_min=200.0, distance_max=500.0,
    )

    assert isinstance(result_full, go.Figure)
    assert isinstance(result_zone, go.Figure)
    # Speed es la traza 0 en ambas figuras
    assert len(result_zone.data[0].x) < len(result_full.data[0].x)


@patch("fastf1.Cache.enable_cache")
@patch("fastf1.get_session")
def test_trace_labels_contain_driver_and_lap_number(mock_get_session, mock_cache):
    """Los nombres de traza incluyen el código del piloto y el número de vuelta."""
    session = _make_session({"COL": [(5, 82.5)]})
    mock_get_session.return_value = session
    result = plot_telemetry_trace(None, "Austrian Grand Prix", 2026, ["COL"], "Q")
    assert isinstance(result, go.Figure)
    trace_names = [t.name for t in result.data if t.name]
    assert any("COL" in name for name in trace_names)
    assert any("5" in name for name in trace_names)   # vuelta más rápida es la 5 (82.5s)
