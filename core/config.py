import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── Paths ─────────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR     = PROJECT_ROOT / "data"
CACHE_DIR    = DATA_DIR / "raw"

# ── Season ────────────────────────────────────────────────────────────────────
YEAR = int(os.getenv("YEAR", "2026"))

# ── Claude ────────────────────────────────────────────────────────────────────
ANTHROPIC_MODEL      = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
ANTHROPIC_MAX_TOKENS = int(os.getenv("ANTHROPIC_MAX_TOKENS", "8192"))

# ── Supabase / PostgreSQL ─────────────────────────────────────────────────────
SUPABASE_URL             = os.getenv("SUPABASE_URL", "")
SUPABASE_PUBLISHABLE_KEY = os.getenv("SUPABASE_PUBLISHABLE_KEY", "")
SUPABASE_SECRET_KEY      = os.getenv("SUPABASE_SECRET_KEY", "")
SUPABASE_DB_URL          = os.getenv("SUPABASE_DB_URL", "")

# ── GP name aliases (input del usuario → nombre oficial FastF1) ───────────────
GP_ALIASES: dict[str, str] = {
    "australia":      "Australian Grand Prix",
    "australian":     "Australian Grand Prix",
    "china":          "Chinese Grand Prix",
    "chinese":        "Chinese Grand Prix",
    "japan":          "Japanese Grand Prix",
    "japanese":       "Japanese Grand Prix",
    "miami":          "Miami Grand Prix",
    "monaco":         "Monaco Grand Prix",
    "mónaco":         "Monaco Grand Prix",
    "canada":         "Canadian Grand Prix",
    "canadian":       "Canadian Grand Prix",
    "barcelona":      "Barcelona Grand Prix",
    "españa":         "Barcelona Grand Prix",
    "austria":        "Austrian Grand Prix",
    "austrian":       "Austrian Grand Prix",
    "britain":        "British Grand Prix",
    "british":        "British Grand Prix",
    "silverstone":    "British Grand Prix",
    "belgium":        "Belgian Grand Prix",
    "belgian":        "Belgian Grand Prix",
    "hungary":        "Hungarian Grand Prix",
    "hungarian":      "Hungarian Grand Prix",
    "netherlands":    "Dutch Grand Prix",
    "dutch":          "Dutch Grand Prix",
    "monza":          "Italian Grand Prix",
    "italy":          "Italian Grand Prix",
    "italian":        "Italian Grand Prix",
    "spain":          "Spanish Grand Prix",
    "spanish":        "Spanish Grand Prix",
    "azerbaijan":     "Azerbaijan Grand Prix",
    "baku":           "Azerbaijan Grand Prix",
    "singapore":      "Singapore Grand Prix",
    "usa":            "United States Grand Prix",
    "cota":           "United States Grand Prix",
    "mexico":         "Mexico City Grand Prix",
    "são paulo":      "São Paulo Grand Prix",
    "sao paulo":      "São Paulo Grand Prix",
    "brazil":         "São Paulo Grand Prix",
    "brasil":         "São Paulo Grand Prix",
    "las vegas":      "Las Vegas Grand Prix",
    "qatar":          "Qatar Grand Prix",
    "abu dhabi":      "Abu Dhabi Grand Prix",
}

def normalize_gp_name(name: str) -> str:
    return GP_ALIASES.get(name.strip().lower(), name.strip())

# ── Predefined analysis prompts (shared between CLI and web UI) ───────────────
PREDEFINED_ANALYSES: list[str] = [
    "Resumen del fin de semana",
    "Comparativa de clasificación",
    "Batalla entre compañeros de equipo",
    "Ritmo de carrera por piloto",
    "Degradación de neumáticos",
    "Análisis de pit stops",
    "Undercut / Overcut",
    "Análisis por sectores",
]
