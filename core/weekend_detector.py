import fastf1
from core.config import CACHE_DIR, SPRINT_WEEKENDS
from core.data_extractor import get_session_data

def detect_weekend_type(gp_name: str) -> str:
    return "sprint" if gp_name in SPRINT_WEEKENDS else "normal"

def get_available_sessions(year: int, gp_name: str) -> list[str]:
    """Consulta FastF1 para las sesiones reales del evento. Fallback a lista estática."""
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        fastf1.Cache.enable_cache(str(CACHE_DIR))
        event = fastf1.get_event(year, gp_name)
        sessions = [event.get_session_name(i) for i in range(1, 6)]
        sessions = [s for s in sessions if s]
        return sessions if sessions else _static_sessions(gp_name)
    except Exception:
        return _static_sessions(gp_name)

def _static_sessions(gp_name: str) -> list[str]:
    if gp_name in SPRINT_WEEKENDS:
        return ["FP1", "SQ", "SS", "Q", "R"]
    return ["FP1", "FP2", "FP3", "Q", "R"]

_SESSION_LABELS: dict[str, str] = {
    "FP1": "Practice 1 (FP1)",
    "FP2": "Free Practice 2 (FP2)",
    "FP3": "Free Practice 3 (FP3)",
    "SQ":  "Sprint Qualifying (SQ)",
    "SS":  "Sprint Race (SS)",
    "Q":   "Qualifying (Q)",
    "R":   "Race (R)",
}

def get_session_display_names(gp_name: str) -> list[tuple[str, str]]:
    """Retorna [(código, nombre_completo), ...] para el tipo de fin de semana."""
    codes = _static_sessions(gp_name)
    return [(c, _SESSION_LABELS.get(c, c)) for c in codes]

_INGESTABLE = {"Q", "R", "SQ", "SS"}

def ensure_sessions_loaded(gp_name: str, db, year: int = 2026) -> bool:
    """Verifica que las sesiones con datos en DB estén cargadas; descarga los que falten."""
    any_loaded = False
    for stype in [s for s in _static_sessions(gp_name) if s in _INGESTABLE]:
        if db.session_exists(year, gp_name, stype):
            any_loaded = True
        else:
            result = get_session_data(year, gp_name, session_type=stype)
            if result:
                any_loaded = True
            else:
                print(f"[WARN] No se pudo cargar {stype} para {gp_name} {year}.")
    return any_loaded
