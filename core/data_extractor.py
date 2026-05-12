import fastf1
import traceback
import pandas as pd
from core.config import CACHE_DIR, YEAR
from core.database_manager import F1Database

def get_session_data(year, gp_name, session_type="R"):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    fastf1.Cache.enable_cache(str(CACHE_DIR))

    db = F1Database()
    all_laps_data = []

    print("Downloading official FIA telemetry...")
    try:
        session = fastf1.get_session(year, gp_name, session_type)
        print("Loading session data (telemetry, weather, messages)...")
        session.load(telemetry=True, weather=True, messages=False)

        print("Generando resumen técnico para el análisis...")
        results_data = session.results.to_dict("records")

        for driver_number in session.drivers:
            driver_laps = session.laps.pick_drivers(driver_number)
            if not driver_laps.empty:
                for index, lap in driver_laps.iterlaps():
                    lap_time_seconds = lap["LapTime"].total_seconds() if pd.notna(lap["LapTime"]) else None
                    s1_time_seconds  = lap["Sector1Time"].total_seconds() if pd.notna(lap["Sector1Time"]) else None
                    s2_time_seconds  = lap["Sector2Time"].total_seconds() if pd.notna(lap["Sector2Time"]) else None
                    s3_time_seconds  = lap["Sector3Time"].total_seconds() if pd.notna(lap["Sector3Time"]) else None

                    all_laps_data.append({
                        "driver":       lap["Driver"],
                        "lap_number":   int(lap["LapNumber"]),
                        "lap_time":     lap_time_seconds,
                        "s1":           s1_time_seconds,
                        "s2":           s2_time_seconds,
                        "s3":           s3_time_seconds,
                        "compound":     lap["Compound"],
                        "tyre_life":    int(lap["TyreLife"]) if pd.notna(lap["TyreLife"]) else None,
                        "stint":        int(lap["Stint"]) if pd.notna(lap["Stint"]) else None,
                        "is_pit_in":    pd.notna(lap["PitInTime"]),
                        "is_pit_out":   pd.notna(lap["PitOutTime"]),
                        "session_type": session_type,
                    })

        print("Processing lap data...")

        if not all_laps_data:
            print(f"[WARN] No se encontraron vueltas para {year} {gp_name} {session_type}.")
            return None

        session_id = db.insert_session(year, gp_name, session_type)
        laps_df = pd.DataFrame(all_laps_data)
        laps_df = laps_df.dropna(subset=["s1", "s2", "s3"])
        db.insert_laps_data(session_id, laps_df)
        print(f"[INFO] {len(laps_df)} laps saved for {year} {gp_name} {session_type}.")

        if session_type == "R" and results_data:
            results_df = pd.DataFrame(results_data)
            results_df["session_id"] = session_id
            db.insert_results_data(session_id, results_df)
            print(f"[INFO] {len(results_df)} results saved for {year} {gp_name} {session_type}.")
        elif session_type == "Q" and results_data:
            qualy_results_df = pd.DataFrame(results_data)
            qualy_results_df["session_id"] = session_id
            db.insert_qualy_results_data(session_id, qualy_results_df)
            print(f"[INFO] {len(qualy_results_df)} qualifying results saved for {year} {gp_name} {session_type}.")

        try:
            weather_data = session.weather_data.iloc[0]
            db.insert_weather_data(session_id, weather_data)
        except Exception:
            print(f"[WARN] Weather data not available for {year} {gp_name} {session_type}.")

        print(f"Data for {year} {gp_name} {session_type} saved to database.")
        return True

    except fastf1.exceptions.DataNotLoadedError as e:
        print(f"[ERROR] FastF1 no pudo cargar datos: {e}")
        return None
    except Exception as e:
        print(f"[ERROR] Error inesperado al descargar {gp_name} {session_type}:")
        traceback.print_exc()
        return None
