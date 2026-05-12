import plotly.graph_objects as go
import pandas as pd

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
