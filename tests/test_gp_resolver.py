import pytest
from core.gp_resolver import parse_gp_input, GPNotFoundError, DEFAULT_YEAR


# ── Tests existentes (mantenidos) ──────────────────────────────────────────────

def test_gp_name_only():
    assert parse_gp_input("Miami") == ("Miami Grand Prix", 2026)


def test_gp_with_year():
    assert parse_gp_input("Miami 2025") == ("Miami Grand Prix", 2025)


def test_gp_accented():
    assert parse_gp_input("Mónaco") == ("Monaco Grand Prix", 2026)


def test_gp_partial_name():
    assert parse_gp_input("Canada") == ("Canadian Grand Prix", 2026)


def test_default_year_is_2026():
    _, year = parse_gp_input("Japan")
    assert year == DEFAULT_YEAR


# ── Nombres desconocidos ───────────────────────────────────────────────────────

def test_unknown_gp_name_passes_through():
    """Un nombre sin alias conocido se devuelve tal cual — sin error."""
    name, year = parse_gp_input("xyzzy 2026")
    assert name == "xyzzy"
    assert year == 2026


def test_completely_unknown_name_no_exception():
    """parse_gp_input nunca lanza GPNotFoundError (eso ocurre en weekend_detector)."""
    name, year = parse_gp_input("asdfgh")
    assert isinstance(name, str)
    assert year == DEFAULT_YEAR


# ── Extracción de año ──────────────────────────────────────────────────────────

def test_year_at_start():
    """Año al inicio del string — se extrae correctamente."""
    name, year = parse_gp_input("2025 Monaco")
    assert year == 2025
    assert name == "Monaco Grand Prix"


def test_year_in_middle():
    name, year = parse_gp_input("Austria 2024 GP")
    assert year == 2024


def test_no_year_uses_default():
    _, year = parse_gp_input("Silverstone")
    assert year == DEFAULT_YEAR


def test_year_four_digits_only():
    """Solo años del formato 20XX se reconocen como año."""
    # "1999" no es 20XX, se trata como parte del nombre
    name, year = parse_gp_input("Miami 1999")
    assert year == DEFAULT_YEAR


# ── Aliases y variantes ────────────────────────────────────────────────────────

def test_alias_baku():
    name, _ = parse_gp_input("Baku")
    assert name == "Azerbaijan Grand Prix"


def test_alias_cota():
    name, _ = parse_gp_input("COTA")
    assert name == "United States Grand Prix"


def test_alias_brazil():
    name, _ = parse_gp_input("Brasil")
    assert name == "São Paulo Grand Prix"


def test_whitespace_stripped():
    name, year = parse_gp_input("  Monaco  ")
    assert name == "Monaco Grand Prix"
    assert year == DEFAULT_YEAR


# ── GPNotFoundError ────────────────────────────────────────────────────────────

def test_gp_not_found_error_is_importable():
    """GPNotFoundError es una excepción concreta, subclase de Exception."""
    assert issubclass(GPNotFoundError, Exception)


def test_gp_not_found_error_can_be_raised_and_caught():
    with pytest.raises(GPNotFoundError, match="no encontrado"):
        raise GPNotFoundError("no encontrado")
