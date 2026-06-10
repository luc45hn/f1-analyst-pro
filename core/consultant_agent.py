import re
import time
import unicodedata
import anthropic
import os
from anthropic import APIStatusError
from datetime import date as _date
from core.config import ANTHROPIC_MODEL, ANTHROPIC_MAX_TOKENS, DAILY_COST_LIMIT_USD
from core.gp_resolver import DEFAULT_YEAR
from core.database_manager import F1Database
from core.chart_builder import (
    plot_lap_times, plot_sector_comparison,
    plot_tyre_degradation, plot_pit_stops,
    plot_telemetry_trace,
)
from core.driver_resolver import get_driver_name_to_code
from core.logger import get_logger

logger = get_logger(__name__)

_OMIT = {"session_id", "session_type"}


def _to_records(df):
    return df.drop(columns=[c for c in _OMIT if c in df.columns]).to_dict("records")


class F1ConsultantAgent:
    def __init__(self):
        self.client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self.db = F1Database()

    def send_message(self, prompt, gp_name, year: int = DEFAULT_YEAR, compare_previous_year: bool = False, user_email: str = "", on_status=None):
        try:
            daily_cost = self.db.get_daily_cost(user_email, _date.today())
            if daily_cost >= DAILY_COST_LIMIT_USD:
                return {
                    "text": "⚠️ Alcanzaste el límite diario de uso ($2.00). El límite se resetea a medianoche. Si necesitás más consultas, contactá al administrador.",
                    "chart": None,
                }
        except Exception:
            pass
        prompt_lower = unicodedata.normalize("NFD", prompt.lower()).encode("ascii", "ignore").decode()

        wants_qualy  = any(w in prompt_lower for w in ["clasif", "qualy", "qualifying", "pole", "q1", "q2", "q3", "grid"])
        wants_race   = any(w in prompt_lower for w in ["carrera", "race", "vuelta", "ritmo", "neumático",
                                                        "stint", "pit", "parada", "degradación", "top"])
        wants_sprint = any(w in prompt_lower for w in ["sprint", "sq", "ss"])
        wants_practice = any(w in prompt_lower for w in [
            "entrenamiento", "practica", "fp1", "fp2", "fp3",
            "practice", "libre", "libres", "evolucion", "setup"
        ])
        wants_undercut = any(w in prompt_lower for w in [
            "undercut", "overcut", "estrategia de pit", "parada",
            "beneficio", "perjudico", "funciono la parada"
        ])
        if wants_sprint and "sq" in prompt_lower:
            wants_qualy = True
        load_all = not (wants_qualy or wants_race or wants_sprint or wants_practice or wants_undercut)
        wants_telemetry = any(w in prompt_lower for w in [
            "telemetria", "trace", "acelerador",
            "freno", "frenar", "clipping", "throttle", "brake",
            "aceleracion", "aceleraciones", "frenada", "frenadas",
            "velocidad", "canal", "canales", "grafica", "grafico",
        ])
        _qs = re.search(r'\b(q[123])\b', prompt_lower)
        qualifying_segment = _qs.group(1).upper() if _qs else None
        logger.debug("intent | gp=%s wants_qualy=%s wants_race=%s wants_sprint=%s load_all=%s wants_telemetry=%s qualifying_segment=%s",
                     gp_name, wants_qualy, wants_race, wants_sprint, load_all, wants_telemetry, qualifying_segment)

        static_context  = f"Gran Premio: {gp_name} — Temporada {year}\n\n"
        missing_context = ""
        sessions_in_context = []

        # --- CLASIFICACIÓN ---
        if wants_qualy or load_all:
            qualy_id = self.db.get_session_id(year, gp_name, "Q")
            if qualy_id:
                sessions_in_context.append("Q")
                best_q = self.db.get_best_lap_per_driver(qualy_id).to_dict("records")
                q_results = _to_records(self.db.get_qualy_results_data(qualy_id))
                if best_q:
                    static_context += "--- MEJOR VUELTA POR PILOTO EN QUALIFYING (Q) ---\n" + str(best_q) + "\n\n"
                if q_results:
                    static_context += "--- RESULTADOS DE QUALIFYING — Q1 / Q2 / Q3 ---\n" + str(q_results) + "\n\n"
            else:
                missing_context += "[SIN DATOS: La sesión Qualifying (Q) no está disponible en la base de datos.]\n\n"

        # --- CARRERA ---
        if wants_race or wants_undercut or load_all:
            race_id = self.db.get_session_id(year, gp_name, "R")
            if race_id:
                sessions_in_context.append("R")
                results_df = self.db.get_results_data(race_id)
                if not results_df.empty:
                    top20 = _to_records(results_df.head(22))
                    static_context += "--- CLASIFICACIÓN FINAL DE CARRERA (R) ---\n" + str(top20) + "\n\n"
                    best_per_driver = self.db.get_best_lap_per_driver(race_id).to_dict("records")
                    if best_per_driver:
                        static_context += "--- MEJOR VUELTA POR PILOTO EN CARRERA (R) ---\n" + str(best_per_driver) + "\n\n"
                race_data = self.db.get_stint_summary(race_id).to_dict("records")
                if race_data:
                    static_context += "--- RESUMEN DE RITMO POR STINT EN CARRERA (R) ---\n" + str(race_data) + "\n\n"
                if wants_undercut or wants_race or load_all:
                    _pit_df = self.db.get_pit_stop_analysis(race_id)
                    if not _pit_df.empty:
                        _pit_cols = ["driver", "pit_lap", "compound_out", "compound_in",
                                     "rival", "stop_order", "delta_vs_rival", "verdict"]
                        static_context += (
                            "--- ANÁLISIS DE UNDERCUT/OVERCUT ---\n"
                            + _pit_df[[c for c in _pit_cols if c in _pit_df.columns]].to_string(index=False)
                            + "\n\n"
                        )
            else:
                missing_context += "[SIN DATOS: La sesión Race (R) no está disponible en la base de datos.]\n\n"

        # --- SPRINT ---
        if wants_sprint or load_all:
            ss_id = self.db.get_session_id(year, gp_name, "SS")
            if ss_id:
                sessions_in_context.append("SS")
                ss_results = self.db.get_results_data(ss_id)
                if not ss_results.empty:
                    static_context += "--- CLASIFICACIÓN FINAL SPRINT RACE (SS) ---\n" + str(_to_records(ss_results.head(22))) + "\n\n"
                top_ss = self.db.get_top_laps(ss_id).to_dict("records")
                if top_ss:
                    static_context += "--- TOP 10 VUELTAS SPRINT RACE (SS) ---\n" + str(top_ss) + "\n\n"

            sq_id = self.db.get_session_id(year, gp_name, "SQ")
            if sq_id:
                sessions_in_context.append("SQ")
                top_sq = self.db.get_top_laps(sq_id).to_dict("records")
                if top_sq:
                    static_context += "--- TOP 10 VUELTAS SPRINT QUALIFYING (SQ) ---\n" + str(top_sq) + "\n\n"

        # --- ENTRENAMIENTOS (FP) ---
        if wants_practice or load_all:
            for fp_code, fp_label in [
                ("FP1", "PRÁCTICA 1 (FP1)"),
                ("FP2", "PRÁCTICA 2 (FP2)"),
                ("FP3", "PRÁCTICA 3 (FP3)"),
            ]:
                fp_id = self.db.get_session_id(year, gp_name, fp_code)
                if fp_id:
                    sessions_in_context.append(fp_code)
                    best_fp = self.db.get_best_lap_per_driver(fp_id).to_dict("records")
                    if best_fp:
                        static_context += f"--- {fp_label} ---\n" + str(best_fp) + "\n\n"

        # --- ALINEACIÓN ---
        lineup_sid = (self.db.get_session_id(year, gp_name, "R")
                      or self.db.get_session_id(year, gp_name, "SS"))
        if lineup_sid:
            lineups = self.db.get_team_lineups(lineup_sid)
            if lineups:
                static_context += "--- ALINEACIÓN DE EQUIPOS (fuente: datos de carrera) ---\n" + str(lineups) + "\n\n"

        # --- COMPARACIÓN AÑO ANTERIOR ---
        comparison_context = ""
        if compare_previous_year:
            prev_year = year - 1
            any_prev = False

            q_id_prev = self.db.get_session_id(prev_year, gp_name, "Q")
            if q_id_prev:
                any_prev = True
                best_q_prev = self.db.get_best_lap_per_driver(q_id_prev).to_dict("records")
                qr_prev = _to_records(self.db.get_qualy_results_data(q_id_prev))
                if best_q_prev:
                    comparison_context += f"--- MEJOR VUELTA POR PILOTO QUALIFYING {prev_year} (COMPARACIÓN) ---\n" + str(best_q_prev) + "\n\n"
                if qr_prev:
                    comparison_context += f"--- RESULTADOS QUALIFYING {prev_year} — Q1/Q2/Q3 (COMPARACIÓN) ---\n" + str(qr_prev) + "\n\n"

            r_id_prev = self.db.get_session_id(prev_year, gp_name, "R")
            if r_id_prev:
                any_prev = True
                res_prev = self.db.get_results_data(r_id_prev)
                if not res_prev.empty:
                    comparison_context += f"--- CLASIFICACIÓN FINAL CARRERA {prev_year} (COMPARACIÓN) ---\n" + str(_to_records(res_prev.head(22))) + "\n\n"
                    best_r_prev = self.db.get_best_lap_per_driver(r_id_prev).to_dict("records")
                    if best_r_prev:
                        comparison_context += f"--- MEJOR VUELTA POR PILOTO CARRERA {prev_year} (COMPARACIÓN) ---\n" + str(best_r_prev) + "\n\n"
                stint_prev = self.db.get_stint_summary(r_id_prev).to_dict("records")
                if stint_prev:
                    comparison_context += f"--- RESUMEN DE RITMO POR STINT CARRERA {prev_year} (COMPARACIÓN) ---\n" + str(stint_prev) + "\n\n"

            ss_id_prev = self.db.get_session_id(prev_year, gp_name, "SS")
            if ss_id_prev:
                any_prev = True
                top_ss_prev = self.db.get_top_laps(ss_id_prev).to_dict("records")
                if top_ss_prev:
                    comparison_context += f"--- TOP 10 VUELTAS SPRINT RACE {prev_year} (COMPARACIÓN) ---\n" + str(top_ss_prev) + "\n\n"

            sq_id_prev = self.db.get_session_id(prev_year, gp_name, "SQ")
            if sq_id_prev:
                any_prev = True
                top_sq_prev = self.db.get_top_laps(sq_id_prev).to_dict("records")
                if top_sq_prev:
                    comparison_context += f"--- TOP 10 VUELTAS SPRINT QUALIFYING {prev_year} (COMPARACIÓN) ---\n" + str(top_sq_prev) + "\n\n"

            if not any_prev:
                missing_context += f"[SIN DATOS: No hay información de {prev_year} disponible para este GP.]\n\n"

        _system_text = (
            "Eres un analista técnico de Fórmula 1 de élite. "
            "Respondes siempre en español con precisión técnica, usando tablas Markdown para datos tabulares "
            "y bloques de cita (>) para conclusiones analíticas. "
            "Destacas con negritas los datos clave. Eres conciso pero riguroso. "
            "Cuando cites datos de una sesión específica, indicá siempre su nombre completo "
            "(ej: Qualifying (Q), Sprint Race (SS), Sprint Qualifying (SQ), Race (R)). "
            "Cuando presentes mejores vueltas de carrera, siempre incluí el número de vuelta (lap_number) "
            "en la tabla junto con tiempo, compuesto y vida del neumático. "
            "En el resumen del fin de semana, incluir siempre una tabla de constructores que muestre "
            "posición de parrilla y posición de carrera para cada piloto, para evidenciar remontadas o caídas. "
            "En el análisis de carrera, destacar siempre al menos un piloto o equipo sorpresa — "
            "ya sea positiva (remontada, ritmo inesperado) o negativa (caída de rendimiento, abandono clave). "
            "Si el contexto indica [SIN DATOS] para una sesión, informá al periodista de forma clara y natural "
            "que no hay datos disponibles para esa sesión, sin asumir si se disputó o no. "
            "Cuando haya datos de dos años disponibles, comparalos directamente en tablas — "
            "tiempos de clasificación, ritmo de carrera, estrategias. "
            "Indicá siempre el año al que pertenece cada dato. "
            "Destacá las diferencias más relevantes entre temporadas. "
            "IMPORTANTE: nunca uses H1, H2 ni H3 en tus respuestas. No pongas el nombre del GP como título. "
            "Empezá directamente con el primer dato o tabla. "
            "Si necesitás un separador de sección, usá texto en negrita en una línea sola, no heading markdown. "
            "Cuando el periodista pregunte sobre telemetría, trace de vuelta, acelerador, freno o clipping, "
            "indicá que vas a mostrar el gráfico y explicá brevemente qué muestra cada canal antes de presentarlo. "
            "Para solicitudes de telemetría, NUNCA verifiques si el piloto aparece en los datos de laps del contexto. "
            "La telemetría se obtiene directamente de FastF1 de forma independiente — simplemente indicá que vas a "
            "mostrar el gráfico y dejá que el sistema lo genere. No rechaces solicitudes de telemetría basándote "
            "en la disponibilidad de datos en el contexto. "
            "Cuando analices sesiones de entrenamiento (FP1, FP2, FP3), enfocate en la evolución "
            "de los tiempos entre sesiones y qué pilotos/equipos mostraron mayor progreso. "
            "Cuando tengas datos de undercut/overcut, presentá un veredicto claro por cada interacción relevante. "
            "Destacá las maniobras que cambiaron posiciones reales y explicá brevemente por qué funcionó o falló "
            "en términos de estrategia."
        )

        if load_all:
            system_param = [
                {
                    "type": "text",
                    "text": _system_text + "\n\nContexto de datos:\n" + static_context,
                    "cache_control": {"type": "ephemeral"},
                }
            ]
            extra = "".join(filter(None, [missing_context, comparison_context]))
            user_content = (extra + "\n" + prompt) if extra else prompt
        else:
            system_param = _system_text
            extra = "".join(filter(None, [missing_context, comparison_context]))
            user_content = f"Contexto de datos:\n{static_context}{extra}\nPregunta: {prompt}"

        _NON_DRIVER = {"SQ", "SS", "FP1", "FP2", "FP3", "DRS", "VSC", "THE", "AND", "FOR"}

        pre_chart = None
        if wants_telemetry:
            try:
                _q_id  = self.db.get_session_id(year, gp_name, "Q")
                _r_id  = self.db.get_session_id(year, gp_name, "R")
                _sq_id = self.db.get_session_id(year, gp_name, "SQ") if wants_sprint else None
                if wants_sprint and _sq_id:
                    _stype = "SQ"
                elif _q_id:
                    _stype = "Q"
                else:
                    _stype = "R"
                _code_map = get_driver_name_to_code(gp_name, year)
                _seen: set[str] = set()
                from_names: list[str] = []
                for _tok in re.findall(r'\b\w+\b', prompt_lower):
                    if _tok in _code_map and _code_map[_tok] not in _seen:
                        _seen.add(_code_map[_tok])
                        from_names.append(_code_map[_tok])
                from_abbr = [w for w in re.findall(r'\b[A-Z]{3}\b', prompt.upper()) if w not in _NON_DRIVER]
                from_prompt = from_names if from_names else from_abbr
                logger.debug("telemetry | from_names=%s from_abbr=%s → from_prompt=%s stype=%s",
                             from_names, from_abbr, from_prompt, _stype)
                if from_prompt:
                    _tel_drivers = from_prompt[:2]
                elif _q_id or _r_id:
                    _laps = self.db.get_laps_data(_q_id or _r_id)
                    _tel_drivers = _laps["driver"].unique().tolist()[:1]
                else:
                    _tel_drivers = []
                logger.debug("telemetry | final drivers=%s session_type=%s", _tel_drivers, _stype)
                if _tel_drivers:
                    if on_status:
                        on_status("📡 Descargando telemetría de FastF1... (puede tardar ~10s)")
                    pre_chart = plot_telemetry_trace(
                        None, gp_name, year, _tel_drivers, _stype,
                        qualifying_segment if _stype == "Q" else None,
                    )
                    if pre_chart is not None:
                        logger.debug("pre_chart OK | drivers=%s session=%s", _tel_drivers, _stype)
                        user_content += (
                            f"\n\n[SISTEMA: El gráfico de telemetría de {' vs '.join(_tel_drivers)} "
                            f"en {_stype} ya fue generado y se mostrará junto a tu respuesta. "
                            "Explicá brevemente qué muestra cada canal (Speed, Throttle, Brake, Gear) "
                            "y qué conclusiones técnicas se pueden sacar. No generes código.]"
                        )
                    else:
                        logger.debug("pre_chart falló o retornó None | drivers=%s session=%s", _tel_drivers, _stype)
            except Exception:
                logger.warning("telemetry chart failed pre-API | gp=%s", gp_name)

        if on_status:
            on_status("🤖 Generando análisis...")
        logger.debug("user_content (primeros 200 chars) | %s", user_content[:200])
        t0 = time.time()
        for attempt in range(3):
            try:
                response = self.client.messages.create(
                    model=ANTHROPIC_MODEL,
                    max_tokens=ANTHROPIC_MAX_TOKENS,
                    system=system_param,
                    messages=[{"role": "user", "content": user_content}]
                )
                break
            except APIStatusError as e:
                if e.status_code == 529 and attempt < 2:
                    time.sleep(5 * (attempt + 1))
                else:
                    raise

        elapsed = time.time() - t0
        usage = response.usage
        cost_usd = (usage.input_tokens / 1_000_000 * 3) + (usage.output_tokens / 1_000_000 * 15)
        cache_write = getattr(usage, "cache_creation_input_tokens", 0) or 0
        cache_read  = getattr(usage, "cache_read_input_tokens", 0) or 0
        logger.info(
            "API call | GP=%s sessions=%s input=%d output=%d "
            "cache_write=%d cache_read=%d cost=$%.4f elapsed=%.2fs",
            gp_name, sessions_in_context, usage.input_tokens, usage.output_tokens,
            cache_write, cache_read, cost_usd, elapsed,
        )
        text = response.content[0].text
        if pre_chart is not None:
            chart = pre_chart
        else:
            try:
                chart = self._build_chart(prompt_lower, gp_name, year)
                if chart is not None:
                    logger.debug("chart generated | gp=%s", gp_name)
            except Exception:
                chart = None
        self.db.log_query(
            user_email=user_email,
            gp_name=gp_name,
            year=year,
            prompt=prompt,
            intent={
                "wants_qualy": wants_qualy,
                "wants_race": wants_race,
                "wants_sprint": wants_sprint,
                "wants_practice": wants_practice,
                "wants_undercut": wants_undercut,
                "wants_telemetry": wants_telemetry,
                "load_all": load_all,
            },
            has_chart=chart is not None,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cost_usd=cost_usd,
            elapsed_seconds=round(elapsed, 2),
        )
        return {"text": text, "chart": chart}

    def _build_chart(self, prompt_lower: str, gp_name: str, year: int):
        race_id  = self.db.get_session_id(year, gp_name, "R")
        qualy_id = self.db.get_session_id(year, gp_name, "Q")

        wants_lap_times = any(w in prompt_lower for w in ["tiempos de vuelta", "lap time", "ritmo de vuelta"])
        wants_sectors   = any(w in prompt_lower for w in ["sector", "sectores"])
        wants_deg       = any(w in prompt_lower for w in ["degradación", "degradacion", "degrad"])
        wants_strategy  = any(w in prompt_lower for w in ["pit", "estrategia", "stint", "undercut", "overcut"])

        if wants_lap_times and race_id:
            laps = self.db.get_laps_data(race_id)
            drivers_in_db = laps["driver"].unique().tolist()
            mentioned = [
                d for d in drivers_in_db
                if re.search(r'\b' + re.escape(d.lower()) + r'\b', prompt_lower)
            ]
            driver = mentioned[0] if mentioned else drivers_in_db[0]
            return plot_lap_times(driver, laps)

        if wants_sectors:
            sid = qualy_id or race_id
            if sid:
                laps = self.db.get_laps_data(sid)
                drivers = laps["driver"].unique().tolist()
                return plot_sector_comparison(drivers, laps)

        if wants_deg and race_id:
            laps = self.db.get_laps_data(race_id)
            drivers = laps["driver"].unique().tolist()
            return plot_tyre_degradation(drivers, laps)

        if wants_strategy and race_id:
            laps = self.db.get_laps_data(race_id)
            return plot_pit_stops(laps)

        return None
