from core.consultant_agent import _detect_intent


def test_quien_mas_rapido_q3():
    result = _detect_intent("¿Quién fue el más rápido en Q3?")
    assert result["wants_qualy"] is True
    assert result["qualifying_segment"] == "Q3"


def test_ritmo_de_carrera():
    result = _detect_intent("Dame el ritmo de carrera")
    assert result["wants_race"] is True


def test_clasificacion_sprint():
    result = _detect_intent("Comparame la clasificación sprint")
    assert result["wants_sprint"] is True
    assert result["wants_qualy"] is True   # SQ activa también qualy


def test_resumen_fin_de_semana():
    result = _detect_intent("Resumen del fin de semana")
    assert result["load_all"] is True


def test_telemetria_colapinto():
    result = _detect_intent("Mostrame la telemetría de Colapinto")
    assert result["wants_telemetry"] is True


def test_practice_session():
    result = _detect_intent("¿Cómo fue Colapinto en FP2?")
    assert result["wants_practice"] is True
    assert result["load_all"] is False


def test_undercut_detection():
    result = _detect_intent("¿El undercut de Hamilton funcionó?")
    assert result["wants_undercut"] is True
    assert result["load_all"] is False


def test_distance_range():
    result = _detect_intent("Mostrame la telemetría entre 2000 y 2600m")
    assert result["distance_min"] == 2000.0
    assert result["distance_max"] == 2600.0


def test_austria_curve_9():
    result = _detect_intent("¿Cómo frena Colapinto en la curva 9?", gp_name="Austrian Grand Prix")
    assert result["distance_min"] == 3800.0
    assert result["distance_max"] == 4100.0


def test_qualifying_segment_q1():
    result = _detect_intent("Mostrame los tiempos de Q1")
    assert result["qualifying_segment"] == "Q1"
    assert result["wants_qualy"] is True


def test_load_all_is_false_when_intent_detected():
    result = _detect_intent("Dame la clasificación")
    assert result["wants_qualy"] is True
    assert result["load_all"] is False
