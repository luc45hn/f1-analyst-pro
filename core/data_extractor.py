import re
import fastf1
import numpy as np
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
        load_messages = session_type in ("R", "SS")
        session.load(laps=True, telemetry=True, weather=True, messages=load_messages)

        actual_year = session.event["EventDate"].year
        if actual_year != year:
            raise ValueError(
                f"No se encontraron datos para {gp_name} {year}. "
                f"FastF1 devolvió el evento de {actual_year}."
            )

        logger.debug("Generating technical summary | %s %s %s", year, gp_name, session_type)
        if not session_type.startswith("FP"):
            results_data = session.results.to_dict("records")
        else:
            results_data = []

        for driver_number in session.drivers:
            driver_laps = session.laps.pick_drivers(driver_number)
            if not driver_laps.empty:
                for _, lap in driver_laps.iterlaps():
                    lap_time_seconds = lap["LapTime"].total_seconds() if pd.notna(lap["LapTime"]) else None
                    s1_time_seconds  = lap["Sector1Time"].total_seconds() if pd.notna(lap["Sector1Time"]) else None
                    s2_time_seconds  = lap["Sector2Time"].total_seconds() if pd.notna(lap["Sector2Time"]) else None
                    s3_time_seconds  = lap["Sector3Time"].total_seconds() if pd.notna(lap["Sector3Time"]) else None

                    all_laps_data.append({
                        "driver":           lap["Driver"],
                        "lap_number":       int(lap["LapNumber"]),
                        "lap_time":         lap_time_seconds,
                        "s1":               s1_time_seconds,
                        "s2":               s2_time_seconds,
                        "s3":               s3_time_seconds,
                        "compound":         lap["Compound"],
                        "tyre_life":        int(lap["TyreLife"]) if pd.notna(lap["TyreLife"]) else None,
                        "stint":            int(lap["Stint"]) if pd.notna(lap["Stint"]) else None,
                        "is_pit_in":        pd.notna(lap["PitInTime"]),
                        "is_pit_out":       pd.notna(lap["PitOutTime"]),
                        "track_status":     str(lap["TrackStatus"]) if pd.notna(lap["TrackStatus"]) else None,
                        "session_type":     session_type,
                        "position":         int(lap["Position"]) if pd.notna(lap.get("Position")) else None,
                        "is_personal_best": bool(lap["IsPersonalBest"]) if pd.notna(lap.get("IsPersonalBest")) else None,
                        "speed_i1":         float(lap["SpeedI1"]) if pd.notna(lap.get("SpeedI1")) else None,
                        "speed_i2":         float(lap["SpeedI2"]) if pd.notna(lap.get("SpeedI2")) else None,
                        "speed_fl":         float(lap["SpeedFL"]) if pd.notna(lap.get("SpeedFL")) else None,
                        "speed_st":         float(lap["SpeedST"]) if pd.notna(lap.get("SpeedST")) else None,
                        "deleted":          bool(lap["Deleted"]) if pd.notna(lap.get("Deleted")) else None,
                        "deleted_reason":   str(lap["DeletedReason"]) if pd.notna(lap.get("DeletedReason")) else None,
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
        elif session_type.startswith("FP"):
            logger.debug("FP session — skipping results insert | %s %s %s", year, gp_name, session_type)

        try:
            weather_data = session.weather_data.iloc[0]
            db.insert_weather_data(session_id, weather_data)
        except Exception:
            logger.warning("Weather data not available | %s %s %s", year, gp_name, session_type)

        if session_type in ("R", "SS"):
            try:
                rcm = session.race_control_messages
                if rcm is not None and not rcm.empty:
                    keywords = ['INVESTIGAT', 'PENALTY', 'PENALISED', 'NO FURTHER INVESTIGATION']
                    filtered = rcm[rcm['Message'].str.contains(
                        '|'.join(keywords), case=False, na=False
                    )]
                    incidents = []
                    for _, row in filtered.iterrows():
                        msg = str(row['Message'])
                        driver_match = re.search(r'\((\w{2,3})\)', msg)
                        car_match    = re.search(r'CAR\s*(\d+)', msg, re.IGNORECASE)
                        msg_upper = msg.upper()
                        if 'PENALTY' in msg_upper or 'PENALISED' in msg_upper:
                            category = 'PENALTY'
                        elif 'NO FURTHER INVESTIGATION' in msg_upper:
                            category = 'NO_ACTION'
                        else:
                            category = 'INVESTIGATION'
                        incidents.append({
                            'session_id': session_id,
                            'driver':     driver_match.group(1) if driver_match else None,
                            'car_number': car_match.group(1)    if car_match    else None,
                            'message':    msg,
                            'category':   category,
                        })
                    if incidents:
                        db.insert_race_incidents(incidents)
                        logger.info("%d race incidents saved | %s %s %s",
                                    len(incidents), year, gp_name, session_type)
            except Exception:
                logger.warning("Race incidents not available | %s %s %s", year, gp_name, session_type)

        if session_type in ("R", "SS"):
            try:
                logger.info("telemetry | block entered | %s", session_type)
                logger.info("telemetry | car_data keys: %s", list(session.car_data.keys())[:3])
                for driver_number in session.drivers:
                    logger.info("telemetry | processing driver %s", driver_number)
                    driver_laps = session.laps.pick_drivers(driver_number)
                    if driver_laps.empty:
                        continue
                    try:
                        drv_car = session.car_data[driver_number].copy()
                    except KeyError:
                        logger.warning("telemetry | no car_data for driver_number=%s", driver_number)
                        continue
                    _drv_code = driver_laps.iloc[0]["Driver"]
                    _valid_laps = (
                        driver_laps[driver_laps["LapTime"].notna()]
                        .sort_values("LapStartTime")
                    )
                    logger.debug("telemetry | driver=%s laps=%d", _drv_code, len(_valid_laps))
                    if _valid_laps.empty:
                        continue

                    # Asignar lap_number a cada punto de telemetría por tiempo (searchsorted)
                    _starts_s = _valid_laps["LapStartTime"].dt.total_seconds().values
                    _ends_s   = _valid_laps["Time"].dt.total_seconds().values
                    _laps_n   = _valid_laps["LapNumber"].astype(int).values
                    _tel_s    = drv_car["SessionTime"].dt.total_seconds().values

                    _idx = np.searchsorted(_starts_s, _tel_s, side="right") - 1
                    _valid_mask = (
                        (_idx >= 0)
                        & (_idx < len(_laps_n))
                        & (_tel_s <= _ends_s[np.clip(_idx, 0, len(_ends_s) - 1)])
                    )
                    drv_car = drv_car[_valid_mask].copy()
                    drv_car["lap_number"] = _laps_n[_idx[_valid_mask]]

                    # Distancia por vuelta: cumsum(speed * dt) reseteado en cada vuelta
                    drv_car["_dt"] = drv_car["SessionTime"].diff().dt.total_seconds()
                    _lap_change = drv_car["lap_number"] != drv_car["lap_number"].shift(1)
                    drv_car.loc[_lap_change, "_dt"] = 0.0
                    drv_car["_dt"] = drv_car["_dt"].fillna(0.0).clip(lower=0.0)
                    drv_car["distance"] = (
                        (drv_car["Speed"] * drv_car["_dt"] * (1000.0 / 3600.0))
                        .groupby(drv_car["lap_number"])
                        .cumsum()
                        .round(2)
                    )

                    # Construir tel_rows vectorialmente
                    drv_car["Brake"]      = drv_car["Brake"].astype(float)
                    drv_car["session_id"] = session_id
                    drv_car["driver"]     = _drv_code
                    _result = drv_car[
                        ["session_id", "driver", "lap_number", "distance",
                         "Speed", "Throttle", "Brake", "nGear"]
                    ].rename(columns={
                        "Speed": "speed", "Throttle": "throttle",
                        "Brake": "brake",  "nGear": "gear",
                    })
                    _result = _result.where(_result.notna(), other=None)
                    tel_rows = _result.to_dict("records")

                    if tel_rows:
                        logger.info("telemetry | driver=%s rows_to_insert=%d", _drv_code, len(tel_rows))
                        db.insert_telemetry(tel_rows)
                        logger.info("telemetry | driver=%s rows=%d saved | %s %s %s",
                                    _drv_code, len(tel_rows), year, gp_name, session_type)
            except Exception:
                logger.exception("Telemetry channel data failed | %s %s %s", year, gp_name, session_type)

        logger.info("END ingesting | %s %s %s — OK", year, gp_name, session_type)
        return True

    except fastf1.exceptions.DataNotLoadedError as e:
        logger.error("FastF1 DataNotLoadedError | %s %s %s: %s", year, gp_name, session_type, e)
        return None
    except Exception:
        logger.exception("Unexpected error ingesting | %s %s %s", year, gp_name, session_type)
        return None
