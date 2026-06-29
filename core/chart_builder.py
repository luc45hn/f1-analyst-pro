import plotly.graph_objects as go
import pandas as pd
from plotly.subplots import make_subplots
from core.logger import get_logger as _get_logger

_log = _get_logger(__name__)

COMPOUND_COLORS = {
    "SOFT":         "#FF3333",
    "MEDIUM":       "#FFD700",
    "HARD":         "#CCCCCC",
    "INTERMEDIATE": "#39B54A",
    "WET":          "#0067FF",
}

TEAM_COLORS = {
    "Mercedes":         "#00D2BE",
    "McLaren":          "#FF8000",
    "Red Bull Racing":  "#3671C6",
    "Ferrari":          "#E8002D",
    "Alpine":           "#FF87BC",
    "Aston Martin":     "#358C75",
    "Williams":         "#64C4FF",
    "Haas":             "#B6BABD",
    "Kick Sauber":      "#52E252",
    "Racing Bulls":     "#6692FF",
}

def plot_lap_times(driver: str, laps_df: pd.DataFrame) -> go.Figure:
    """Línea de tiempos de vuelta por stint, coloreada por compuesto."""
    df = laps_df[laps_df["driver"] == driver].copy()
    df = df[df["lap_time"].notna()].sort_values("lap_number")

    fig = go.Figure()
    for compound in df["compound"].dropna().unique():
        sub = df[df["compound"] == compound]
        color = COMPOUND_COLORS.get(compound, "#AAAAAA")
        fig.add_trace(go.Scatter(
            x=sub["lap_number"],
            y=sub["lap_time"],
            mode="lines+markers",
            name=compound,
            line=dict(color=color, width=2),
            marker=dict(color=color, size=5),
        ))

    fig.update_layout(
        title=f"Tiempos de vuelta — {driver}",
        xaxis_title="Vuelta",
        yaxis_title="Tiempo (s)",
        template="plotly_dark",
        legend_title="Compuesto",
    )
    return fig


def plot_sector_comparison(drivers: list[str], session_df: pd.DataFrame) -> go.Figure:
    """Barras agrupadas S1/S2/S3 con la mejor vuelta de cada piloto."""
    df = session_df[session_df["driver"].isin(drivers)].copy()
    df = df[df["lap_time"].notna()]
    best = df.loc[df.groupby("driver")["lap_time"].idxmin()].set_index("driver")

    fig = go.Figure()
    for col, label, color in [
        ("s1", "Sector 1", "#4C9BE8"),
        ("s2", "Sector 2", "#E84C4C"),
        ("s3", "Sector 3", "#4CE88A"),
    ]:
        fig.add_trace(go.Bar(
            name=label,
            x=best.index.tolist(),
            y=best[col].tolist(),
            marker_color=color,
        ))

    fig.update_layout(
        barmode="group",
        title="Comparativa por sectores (mejor vuelta)",
        xaxis_title="Piloto",
        yaxis_title="Tiempo (s)",
        template="plotly_dark",
        legend_title="Sector",
    )
    return fig


def plot_tyre_degradation(drivers: list[str], laps_df: pd.DataFrame) -> go.Figure:
    """Línea de degradación por piloto, stint y compuesto."""
    df = laps_df[laps_df["driver"].isin(drivers)].copy()
    df = df[df["lap_time"].notna() & df["tyre_life"].notna()]

    fig = go.Figure()
    for driver in drivers:
        for compound in df[df["driver"] == driver]["compound"].dropna().unique():
            sub = df[(df["driver"] == driver) & (df["compound"] == compound)].sort_values("tyre_life")
            if sub.empty:
                continue
            color = COMPOUND_COLORS.get(compound, "#AAAAAA")
            fig.add_trace(go.Scatter(
                x=sub["tyre_life"],
                y=sub["lap_time"],
                mode="lines+markers",
                name=f"{driver} — {compound}",
                line=dict(color=color, width=2),
                marker=dict(size=4),
            ))

    fig.update_layout(
        title="Degradación de neumáticos",
        xaxis_title="Vida del neumático (vueltas)",
        yaxis_title="Tiempo de vuelta (s)",
        template="plotly_dark",
    )
    return fig


def plot_pit_stops(laps_df: pd.DataFrame) -> go.Figure:
    """Diagrama de estrategia: stints por piloto como barras horizontales."""
    df = laps_df[laps_df["lap_time"].notna()].copy()
    drivers = df["driver"].unique().tolist()

    fig = go.Figure()
    plotted_compounds: set[str] = set()

    for driver in drivers:
        drv = df[df["driver"] == driver].sort_values("lap_number")
        if drv.empty:
            continue
        drv = drv.copy()
        if drv["stint"].isna().all():
            # Fallback: reconstruct stints from pit-out laps when stint column is NULL
            drv["stint_id"] = drv["is_pit_out"].fillna(False).astype(int).cumsum() + 1
        else:
            drv["stint_id"] = (drv["stint"] != drv["stint"].shift()).cumsum()

        for _, stint in drv.groupby("stint_id"):
            compound = stint["compound"].iloc[0] if pd.notna(stint["compound"].iloc[0]) else "UNKNOWN"
            color = COMPOUND_COLORS.get(compound, "#888888")
            show_legend = compound not in plotted_compounds
            plotted_compounds.add(compound)

            fig.add_trace(go.Bar(
                name=compound,
                x=[len(stint)],
                y=[driver],
                orientation="h",
                base=int(stint["lap_number"].min()) - 1,
                marker_color=color,
                showlegend=show_legend,
                legendgroup=compound,
            ))

    fig.update_layout(
        barmode="stack",
        title="Estrategia de carrera",
        xaxis_title="Vuelta",
        yaxis_title="Piloto",
        template="plotly_dark",
        legend_title="Compuesto",
        height=max(400, len(drivers) * 30),
    )
    return fig


_DRIVER_COLORS      = ["#E24B4A", "#378ADD"]
_DRIVER_FILL_COLORS = ["rgba(226,75,74,0.15)", "rgba(55,138,221,0.15)"]
_FF1_SESSION_MAP = {"SS": "Sprint", "SQ": "Sprint Qualifying"}


def get_telemetry_zone_table(
    gp_name: str,
    year: int,
    driver: str,
    session_type: str,
    lap_numbers: list[int],
    distance_min: float,
    distance_max: float,
) -> pd.DataFrame | None:
    import fastf1
    from core.config import CACHE_DIR

    ff1_identifier = _FF1_SESSION_MAP.get(session_type, session_type)
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        fastf1.Cache.enable_cache(str(CACHE_DIR))
        session = fastf1.get_session(year, gp_name, ff1_identifier)
        session.load(laps=True, telemetry=True, weather=False, messages=False)
    except Exception as e:
        _log.exception("telemetry_zone_table | session load failed | %s", e)
        return None

    drv_laps = session.laps[session.laps["Driver"] == driver]
    zones: list[tuple[int, pd.DataFrame]] = []
    for lap_number in lap_numbers:
        try:
            lap = drv_laps[drv_laps["LapNumber"] == lap_number].iloc[0]
            tel = lap.get_car_data().add_distance()
            tel = tel[(tel["Distance"] >= distance_min) & (tel["Distance"] <= distance_max)]
            zones.append((lap_number, tel[["Distance", "Throttle", "Speed"]].reset_index(drop=True)))
        except Exception as e:
            _log.warning("telemetry_zone_table | lap=%s failed | %s", lap_number, e)
            continue

    if not zones:
        return None

    if len(zones) == 1:
        return zones[0][1]

    table = zones[0][1][["Distance"]].copy()
    for lap_number, tel in zones:
        table[f"Throttle_V{lap_number}"] = tel["Throttle"]
        table[f"Speed_V{lap_number}"] = tel["Speed"]
    return table


def plot_telemetry_trace(
    laps_data,
    gp_name: str,
    year: int,
    drivers: list[str],
    session_type: str = "Q",
    qualifying_segment: str | None = None,
    distance_min: float | None = None,
    distance_max: float | None = None,
) -> go.Figure | None:
    import fastf1
    from core.config import CACHE_DIR

    drivers = drivers[:2]
    ff1_identifier = _FF1_SESSION_MAP.get(session_type, session_type)
    _log.debug("telemetry | gp=%s year=%d drivers=%s session_type=%s → ff1=%s",
               gp_name, year, drivers, session_type, ff1_identifier)
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        fastf1.Cache.enable_cache(str(CACHE_DIR))
        session = fastf1.get_session(year, gp_name, ff1_identifier)
        _log.debug("telemetry | get_session OK → %s", session.name)
        session.load(laps=True, telemetry=True, weather=False, messages=False)
        _log.debug("telemetry | session.load OK | laps=%d", len(session.laps))
    except Exception as e:
        _log.exception("telemetry | session load failed | %s", e)
        return None

    fig = make_subplots(
        rows=4, cols=1, shared_xaxes=True,
        subplot_titles=["Speed (km/h)", "Throttle (%)", "Brake", "Gear"],
        vertical_spacing=0.06,
    )

    compare_laps_mode = qualifying_segment == "Q3" and len(drivers) == 1
    entries: list[tuple[str, "pd.Series", str, str]] = []

    if compare_laps_mode:
        drv = drivers[0]
        try:
            drv_laps = session.laps[session.laps["Driver"] == drv]
            q3_laps = drv_laps[
                drv_laps["LapTime"].notna()
                & (drv_laps["LapTime"].dt.total_seconds() <= 120)
            ]
        except Exception as e:
            _log.warning("telemetry | compare-laps lookup failed | driver=%s | %s", drv, e)
            q3_laps = pd.DataFrame()
        if q3_laps.empty:
            _log.debug("telemetry | no valid laps for compare mode | driver=%s", drv)
            compare_laps_mode = False
        else:
            top_laps = q3_laps.sort_values("LapTime").head(2)
            for idx, (_, lap) in enumerate(top_laps.iterrows()):
                label = f"{drv} — Vuelta {int(lap['LapNumber'])} ({lap['LapTime'].total_seconds():.3f}s)"
                entries.append((label, lap, _DRIVER_COLORS[idx], _DRIVER_FILL_COLORS[idx]))

    if not compare_laps_mode:
        for i, drv in enumerate(drivers):
            color = _DRIVER_COLORS[i]
            fill_color = _DRIVER_FILL_COLORS[i]
            try:
                drv_laps = session.laps[session.laps["Driver"] == drv]
                _log.debug("telemetry | driver=%s laps_found=%d", drv, len(drv_laps))
                if drv_laps.empty:
                    _log.warning("telemetry | no laps for driver=%s", drv)
                    continue
                if qualifying_segment:
                    _stint_map = {"Q1": 1, "Q2": 2, "Q3": 3}
                    _seg_laps = drv_laps[drv_laps["Stint"] == _stint_map[qualifying_segment]]
                    drv_laps = _seg_laps if not _seg_laps.empty else drv_laps
                lap = drv_laps.loc[drv_laps["LapTime"].idxmin()]
            except Exception as e:
                _log.warning("telemetry | driver=%s failed | %s", drv, e)
                continue
            entries.append((drv, lap, color, fill_color))

    for label, lap, color, fill_color in entries:
        try:
            tel = lap.get_car_data().add_distance()
            if distance_min is not None and distance_max is not None:
                tel = tel[(tel["Distance"] >= distance_min) & (tel["Distance"] <= distance_max)]
            _log.debug("telemetry | car_data OK | label=%s points=%d", label, len(tel))
        except Exception as e:
            _log.warning("telemetry | label=%s failed | %s", label, e)
            continue

        x = tel["Distance"]

        try:
            fig.add_trace(go.Scatter(
                x=x, y=tel["Speed"], name=label,
                line=dict(color=color, width=1.5),
                legendgroup=label, showlegend=True,
            ), row=1, col=1)
        except Exception as e:
            _log.warning("telemetry | subplot Speed failed | label=%s | %s", label, e)

        try:
            fig.add_trace(go.Scatter(
                x=x, y=tel["Throttle"], name=label,
                line=dict(color=color, width=1.5),
                fill="tozeroy", fillcolor=fill_color,
                legendgroup=label, showlegend=False,
            ), row=2, col=1)
        except Exception as e:
            _log.warning("telemetry | subplot Throttle failed | label=%s | %s", label, e)

        try:
            brake_y = (tel["Brake"].astype(int) * 100).clip(0, 100)
            fig.add_trace(go.Scatter(
                x=x, y=brake_y, name=label,
                line=dict(color=color, width=1.5),
                fill="tozeroy", fillcolor=fill_color,
                legendgroup=label, showlegend=False,
            ), row=3, col=1)
        except Exception as e:
            _log.warning("telemetry | subplot Brake failed | label=%s | %s", label, e)

        try:
            fig.add_trace(go.Scatter(
                x=x, y=tel["nGear"], name=label,
                line=dict(color=color, width=1.5),
                legendgroup=label, showlegend=False,
            ), row=4, col=1)
        except Exception as e:
            _log.warning("telemetry | subplot Gear failed | label=%s | %s", label, e)

    title_drivers = entries[0][0].split(" — ")[0] if compare_laps_mode and entries else " vs ".join(drivers)
    fig.update_layout(
        title=f'Telemetría — {title_drivers} · {session_type} {gp_name} {year}',
        template="plotly_dark",
        height=700,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    fig.update_xaxes(title_text="Distancia (m)", row=4, col=1)
    _log.debug("telemetry | figure built OK | traces=%d", len(fig.data))
    return fig


def plot_race_sim_pace(
    pace_df: pd.DataFrame,
    driver_team_map: dict,
    gp_name: str,
    year: int,
    session_type: str = "FP2",
    by: str = "team",
) -> go.Figure:
    if pace_df.empty:
        return go.Figure()

    df = pace_df.copy()
    if by == "team":
        df["team"] = df["driver"].map(driver_team_map)
        df = df.dropna(subset=["team"])
        grouped = df.groupby("team")["median_lap_time"].min().reset_index()
        grouped = grouped.sort_values("median_lap_time", ascending=True).reset_index(drop=True)
        labels = grouped["team"].tolist()
        times  = grouped["median_lap_time"].tolist()
        colors = [TEAM_COLORS.get(t, "#AAAAAA") for t in labels]
    else:
        df = df.sort_values("median_lap_time", ascending=True).reset_index(drop=True)
        labels = df["driver"].tolist()
        times  = df["median_lap_time"].tolist()
        colors = [TEAM_COLORS.get(driver_team_map.get(d, ""), "#4C9BE8") for d in labels]

    fastest = times[0]
    gaps = [t - fastest for t in times]
    pcts = [(g / fastest) * 100 for g in gaps]
    text_labels = [
        f"REF  {fastest:.3f}s" if g == 0 else f"+{g:.3f}s  ({p:.2f}%)"
        for g, p in zip(gaps, pcts)
    ]

    fig = go.Figure(go.Bar(
        x=gaps,
        y=labels,
        orientation="h",
        marker_color=colors,
        text=text_labels,
        textposition="outside",
    ))
    fig.update_layout(
        title=f"Race Simulation Pace (estimado) — {session_type} {gp_name} {year}",
        xaxis_title="Gap al más rápido (s)",
        yaxis=dict(autorange="reversed"),
        template="plotly_dark",
        margin=dict(r=200),
        height=max(400, len(labels) * 38),
    )
    return fig
