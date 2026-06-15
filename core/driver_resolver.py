import fastf1
from core.config import CACHE_DIR

_driver_cache: dict = {}
_team_cache: dict = {}


def get_driver_name_to_code(gp_name: str, year: int = 2026) -> dict:
    key = (year, gp_name)
    if key in _driver_cache:
        return _driver_cache[key]
    mapping = {}
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        fastf1.Cache.enable_cache(str(CACHE_DIR))
        for session_name in ["Sprint Qualifying", "Qualifying", "Race", "Sprint"]:
            try:
                session = fastf1.get_session(year, gp_name, session_name)
                session.load(laps=False, telemetry=False, weather=False, messages=False)
                for drv in session.drivers:
                    info = session.get_driver(drv)
                    code = info.get("Abbreviation", "").upper()
                    if not code:
                        continue
                    if first := info.get("FirstName", "").lower():
                        mapping[first] = code
                    if last := info.get("LastName", "").lower():
                        mapping[last] = code
                    mapping[code.lower()] = code
                break
            except Exception:
                continue
    except Exception:
        pass
    _driver_cache[key] = mapping
    return mapping


def get_driver_team_map(gp_name: str, year: int = 2026) -> dict:
    key = (year, gp_name)
    if key in _team_cache:
        return _team_cache[key]
    mapping = {}
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        fastf1.Cache.enable_cache(str(CACHE_DIR))
        for session_name in ["Sprint Qualifying", "Qualifying", "Race", "Sprint"]:
            try:
                session = fastf1.get_session(year, gp_name, session_name)
                session.load(laps=False, telemetry=False, weather=False, messages=False)
                for drv in session.drivers:
                    info = session.get_driver(drv)
                    code = info.get("Abbreviation", "").upper()
                    team = info.get("TeamName", "")
                    if code and team:
                        mapping[code] = team
                break
            except Exception:
                continue
    except Exception:
        pass
    _team_cache[key] = mapping
    return mapping
