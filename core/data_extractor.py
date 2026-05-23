import fastf1
import pandas as pd
from core.config import CACHE_DIR
from core.database_manager import F1Database
from core.logger import get_logger

logger = get_logger(__name__)

_FASTF1_SESSION_MAP = {
    "SS": "Sprint",
}

def get_session_data(year, gp_name, session_type="R"):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    fastf1.Cache.enable_cache(str(CACHE_DIR))

    db = F1Database()
    all_laps_data = []

    logger.info("START ingesting | %s %s %s", year, gp_name, session_type)
    try:
        ff1_identifier = _FASTF1_SESSION_MAP.get(session_type, session_type)
        session = fastf1.get_session(year, gp_name, ff1_identifier)
        logger.info("Loading session data (telemetry, weather) | %s %s %s", year, gp_name, session_type)
        session.load(telemetry=True, weather=True, messages=False)

        actual_year = session.event["EventDate"].year
        if actual_year != year:
            raise ValueError(
                f"No se encontraron datos para {gp_name} {year}. "
                f"FastF1 devolvió el evento de {actual_year}."
            )

        logger.debug("Generating technical summary | %s %s %s", year, gp_name, session_type)
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
                        "track_status": str(lap["TrackStatus"]) if pd.notna(lap["TrackStatus"]) else None,
                        "session_type": session_type,
                    })

        logger.debug("Processing lap data | %s %s %s", year, gp_name, session_type)

        if not all_laps_data:
            logger.warning("No laps found | %s %s %s", year, gp_name, session_type)
            return None

        session_id = db.insert_session(year, gp_name, session_type)
        laps_df = pd.DataFrame(all_laps_data)
        laps_df = laps_df.dropna(subset=["s1", "s2", "s3"])
        db.insert_laps_data(session_id, laps_df)
        logger.info("%d laps saved | %s %s %s", len(laps_df), year, gp_name, session_type)

        if session_type == "R" and results_data:
            results_df = pd.DataFrame(results_data)
            results_df["session_id"] = session_id
            db.insert_results_data(session_id, results_df)
            logger.info("%d results saved | %s %s %s", len(results_df), year, gp_name, session_type)
        elif session_type == "Q" and results_data:
            qualy_results_df = pd.DataFrame(results_data)
            qualy_results_df["session_id"] = session_id
            db.insert_qualy_results_data(session_id, qualy_results_df)
            logger.info("%d qualifying results saved | %s %s %s", len(qualy_results_df), year, gp_name, session_type)
        elif session_type == "SS" and results_data:
            results_df = pd.DataFrame(results_data)
            results_df["session_id"] = session_id
            db.insert_results_data(session_id, results_df)
            logger.info("%d sprint race results saved | %s %s %s", len(results_df), year, gp_name, session_type)
        elif session_type == "SQ" and results_data:
            qualy_results_df = pd.DataFrame(results_data)
            qualy_results_df = qualy_results_df[qualy_results_df["Position"].notna()]
            if qualy_results_df.empty:
                logger.warning("SQ results have no valid positions — skipping insert | %s %s", year, gp_name)
            else:
                qualy_results_df["session_id"] = session_id
                db.insert_qualy_results_data(session_id, qualy_results_df)
                logger.info("%d sprint qualifying results saved | %s %s %s", len(qualy_results_df), year, gp_name, session_type)

        try:
            weather_data = session.weather_data.iloc[0]
            db.insert_weather_data(session_id, weather_data)
        except Exception:
            logger.warning("Weather data not available | %s %s %s", year, gp_name, session_type)

        logger.info("END ingesting | %s %s %s — OK", year, gp_name, session_type)
        return True

    except fastf1.exceptions.DataNotLoadedError as e:
        logger.error("FastF1 DataNotLoadedError | %s %s %s: %s", year, gp_name, session_type, e)
        return None
    except Exception:
        logger.exception("Unexpected error ingesting | %s %s %s", year, gp_name, session_type)
        return None
