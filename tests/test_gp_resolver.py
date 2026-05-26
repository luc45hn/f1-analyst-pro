from core.gp_resolver import parse_gp_input


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
    assert year == 2026
