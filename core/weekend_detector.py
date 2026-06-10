import fastf1
from core.config import CACHE_DIR
from core.data_extractor import get_session_data
from core.gp_resolver import GPNotFoundError
from core.logger import get_logger

_log = get_logger(__name__)

_event_cache: dict[tuple, object] = {}


def _get_event(year: int, gp_name: str):
    key = (year, gp_name)
    if key not in _event_cache:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        fastf1.Cache.enable_cache(str(CACHE_DIR))
        try:
            event = fastf1.get_event(year, gp_name)
        except ValueError as e:
            raise GPNotFoundError(str(e)) from e
        event_name = event.get("EventName", "") or ""
        if not event_name.strip():
            raise GPNotFoundError(f"No se encontró un evento válido para '{gp_name}' {year}.")
        _event_cache[key] = event
    return _event_cache[key]


def detect_weekend_type(gp_name: str, year: int = 2026) -> str:
    try:
        fmt = _get_event(year, gp_name)["EventFormat"]
        return "sprint" if "sprint" in fmt.lower() else "normal"
    except Exception:
        _log.warning("could not detect weekend format | %s %s — defaulting to normal", year, gp_name)
        return "normal"


_NAME_TO_CODE: dict[str, str] = {
    "Practice 1":        "FP1",
    "Practice 2":        "FP2",
    "Practice 3":        "FP3",
    "Sprint Qualifying": "SQ",
    "Sprint Shootout":   "SQ",
    "Sprint":            "SS",
    "Qualifying":        "Q",
    "Race":              "R",
}


def _get_sessions(gp_name: str, year: int = 2026) -> list[str]:
    try:
        event = _get_event(year, gp_name)
        names = [event.get_session_name(i) for i in range(1, 6)]
        return [_NAME_TO_CODE[n] for n in names if n in _NAME_TO_CODE]
    except GPNotFoundError:
        raise
    except Exception:
        return _fallback_sessions(gp_name, year)


def _fallback_sessions(gp_name: str, year: int = 2026) -> list[str]:
    wtype = detect_weekend_type(gp_name, year)
    return ["FP1", "SQ", "SS", "Q", "R"] if wtype == "sprint" else ["FP1", "FP2", "FP3", "Q", "R"]


_SESSION_LABELS: dict[str, str] = {
    "FP1": "Practice 1 (FP1)",
    "FP2": "Free Practice 2 (FP2)",
    "FP3": "Free Practice 3 (FP3)",
    "SQ":  "Sprint Qualifying (SQ)",
    "SS":  "Sprint Race (SS)",
    "Q":   "Qualifying (Q)",
    "R":   "Race (R)",
}


def get_session_display_names(gp_name: str, year: int = 2026) -> list[tuple[str, str]]:
    codes = _get_sessions(gp_name, year)
    return [(c, _SESSION_LABELS.get(c, c)) for c in codes]


_INGESTABLE = {"FP1", "FP2", "FP3", "Q", "R", "SQ", "SS"}


def ensure_sessions_loaded(gp_name: str, db, year: int = 2026) -> tuple[bool, int, int]:
    """Verifica que las sesiones con datos en DB estén cargadas; descarga los que falten.

    Returns (any_loaded, loaded_count, total_count).
    """
    any_loaded   = False
    loaded_count = 0
    total        = 0
    for stype in [s for s in _get_sessions(gp_name, year) if s in _INGESTABLE]:
        total += 1
        if db.session_exists(year, gp_name, stype):
            any_loaded = True
            loaded_count += 1
        else:
            result = get_session_data(year, gp_name, session_type=stype)
            if result:
                any_loaded = True
                loaded_count += 1
            else:
                _log.warning("session not available | %s %s %s — continuando", year, gp_name, stype)
    return any_loaded, loaded_count, total
