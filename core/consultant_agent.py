import re
import anthropic
import os
from core.config import YEAR, ANTHROPIC_MODEL, ANTHROPIC_MAX_TOKENS
from core.database_manager import F1Database
from core.chart_builder import (
    plot_lap_times, plot_sector_comparison,
    plot_tyre_degradation, plot_pit_stops,
)

class F1ConsultantAgent:
    def __init__(self):
        self.client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self.db = F1Database()

    def send_message(self, prompt, gp_name):
        prompt_lower = prompt.lower()

        wants_qualy  = any(w in prompt_lower for w in ["clasif", "qualy", "pole", "q1", "q2", "q3", "grid"])
        wants_race   = any(w in prompt_lower for w in ["carrera", "race", "vuelta", "ritmo", "neumático",
                                                        "stint", "pit", "parada", "degradación", "top"])
        wants_sprint = any(w in prompt_lower for w in ["sprint", "sq", "ss"])
        load_all = not (wants_qualy or wants_race or wants_sprint)

        context_str = f"Gran Premio: {gp_name} — Temporada {YEAR}\n\n"

        # --- CLASIFICACIÓN ---
        if wants_qualy or load_all:
            qualy_id = self.db.get_session_id(YEAR, gp_name, "Q")
            if qualy_id:
                _q_df    = self.db.get_laps_data(qualy_id)
                _q_clean = _q_df.dropna(subset=["lap_time"])
                best_q   = _q_clean.loc[_q_clean.groupby("driver")["lap_time"].idxmin()].to_dict("records")
                q_results = self.db.get_qualy_results_data(qualy_id).to_dict("records")
                if best_q:
                    context_str += "--- MEJOR VUELTA POR PILOTO EN CLASIFICACIÓN ---\n" + str(best_q) + "\n\n"
                if q_results:
                    context_str += "--- RESULTADOS DE CLASIFICACIÓN (Q1/Q2/Q3) ---\n" + str(q_results) + "\n\n"
            else:
                context_str += "ERROR: No hay datos de clasificación en la DB para este GP\n\n"

        # --- CARRERA ---
        if wants_race or load_all:
            race_id = self.db.get_session_id(YEAR, gp_name, "R")
            if race_id:
                all_laps   = self.db.get_laps_data(race_id)
                results_df = self.db.get_results_data(race_id)
                if not results_df.empty:
                    top20 = results_df.head(20).to_dict("records")
                    context_str += "--- CLASIFICACIÓN FINAL ---\n" + str(top20) + "\n\n"
                    best_per_driver = []
                    for row in top20:
                        drv = row["driver"]
                        bl  = all_laps[all_laps["driver"] == drv].nsmallest(1, "lap_time")
                        if not bl.empty:
                            best_per_driver.append(bl.iloc[0].to_dict())
                    if best_per_driver:
                        context_str += "--- MEJOR VUELTA POR PILOTO ---\n" + str(best_per_driver) + "\n\n"
                race_laps_clean = all_laps.dropna(subset=["lap_time"])
                race_data = (
                    race_laps_clean
                    .groupby("driver", group_keys=False)
                    .apply(lambda x: x.nsmallest(10, "lap_time"), include_groups=False)
                    .reset_index(drop=True)
                    .to_dict("records")
                )
                if race_data:
                    context_str += "--- TOP 10 VUELTAS POR PILOTO ---\n" + str(race_data) + "\n\n"
            else:
                context_str += "ERROR: No hay datos de carrera en la DB para este GP\n\n"

        # --- SPRINT ---
        if wants_sprint or load_all:
            for stype, label in [("SQ", "SPRINT QUALIFYING"), ("SS", "SPRINT")]:
                sid = self.db.get_session_id(YEAR, gp_name, stype)
                if sid:
                    s_laps = self.db.get_laps_data(sid).dropna(subset=["lap_time"])
                    top_s  = s_laps.nsmallest(10, "lap_time").to_dict("records")
                    context_str += f"--- TOP 10 VUELTAS {label} ---\n" + str(top_s) + "\n\n"

        system_prompt = (
            "Eres un analista técnico de Fórmula 1 de élite. "
            "Respondes siempre en español con precisión técnica, usando tablas Markdown para datos tabulares "
            "y bloques de cita (>) para conclusiones analíticas. "
            "Destacas con negritas los datos clave. Eres conciso pero riguroso."
        )

        response = self.client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=ANTHROPIC_MAX_TOKENS,
            system=system_prompt,
            messages=[{"role": "user", "content": f"Contexto de datos:\n{context_str}\n\nPregunta: {prompt}"}]
        )
        text = response.content[0].text
        try:
            chart = self._build_chart(prompt_lower, gp_name)
        except Exception:
            chart = None
        return {"text": text, "chart": chart}

    def _build_chart(self, prompt_lower: str, gp_name: str):
        race_id  = self.db.get_session_id(YEAR, gp_name, "R")
        qualy_id = self.db.get_session_id(YEAR, gp_name, "Q")

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
