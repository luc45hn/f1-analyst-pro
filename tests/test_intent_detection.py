import unicodedata


def detect_intent(prompt: str) -> dict:
    """Lógica de detección de intent extraída de F1ConsultantAgent.send_message."""
    prompt_lower = (
        unicodedata.normalize("NFD", prompt.lower())
        .encode("ascii", "ignore")
        .decode()
    )
    wants_qualy = any(
        w in prompt_lower
        for w in ["clasif", "qualy", "qualifying", "pole", "q1", "q2", "q3", "grid"]
    )
    wants_race = any(
        w in prompt_lower
        for w in ["carrera", "race", "vuelta", "ritmo", "neumatico",
                  "stint", "pit", "parada", "degradacion", "top"]
    )
    wants_sprint = any(w in prompt_lower for w in ["sprint", "sq", "ss"])
    if wants_sprint and "sq" in prompt_lower:
        wants_qualy = True
    load_all = not (wants_qualy or wants_race or wants_sprint)
    wants_telemetry = any(
        w in prompt_lower
        for w in ["telemetria", "trace", "acelerador", "freno", "frenar",
                  "clipping", "throttle", "brake"]
    )
    return {
        "wants_qualy": wants_qualy,
        "wants_race": wants_race,
        "wants_sprint": wants_sprint,
        "wants_telemetry": wants_telemetry,
        "load_all": load_all,
    }


def test_quien_mas_rapido_q3():
    result = detect_intent("¿Quién fue el más rápido en Q3?")
    assert result["wants_qualy"] is True


def test_ritmo_de_carrera():
    result = detect_intent("Dame el ritmo de carrera")
    assert result["wants_race"] is True


def test_clasificacion_sprint():
    result = detect_intent("Comparame la clasificación sprint")
    assert result["wants_sprint"] is True
    assert result["wants_qualy"] is True


def test_resumen_fin_de_semana():
    result = detect_intent("Resumen del fin de semana")
    assert result["load_all"] is True


def test_telemetria_colapinto():
    result = detect_intent("Mostrame la telemetría de Colapinto")
    assert result["wants_telemetry"] is True
