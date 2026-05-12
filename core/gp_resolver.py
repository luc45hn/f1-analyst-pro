import re
from core.config import normalize_gp_name

DEFAULT_YEAR = 2026

def parse_gp_input(user_input: str) -> tuple[str, int]:
    """Extrae (gp_name, year) del input del usuario.
    Si no hay año explícito, retorna DEFAULT_YEAR (2026).
    """
    text = user_input.strip()
    year_match = re.search(r'\b(20\d{2})\b', text)
    if year_match:
        year = int(year_match.group(1))
        name_part = (text[:year_match.start()] + text[year_match.end():]).strip()
    else:
        year = DEFAULT_YEAR
        name_part = text
    return normalize_gp_name(name_part), year
