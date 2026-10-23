import os
import re
import logging
from pathlib import Path

_log = logging.getLogger(__name__)

_BUCKET = "f1-analyst-cache"

_FF1_SESSION_NAMES = {
    "R":   "Race",
    "Q":   "Qualifying",
    "SS":  "Sprint",
    "SQ":  "Sprint_Qualifying",
    "FP1": "Practice_1",
    "FP2": "Practice_2",
    "FP3": "Practice_3",
}


def _get_client():
    account_id = os.getenv("R2_ACCOUNT_ID")
    access_key = os.getenv("R2_ACCESS_KEY_ID")
    secret_key = os.getenv("R2_SECRET_ACCESS_KEY")
    if not all([account_id, access_key, secret_key]):
        _log.warning("r2 | credentials not set — skipping R2 cache")
        return None
    import boto3
    return boto3.client(
        "s3",
        endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name="auto",
    )


def _local_session_dir(year: int, event_name: str, session_type: str, cache_dir: str) -> Path | None:
    """Encuentra el subdirectorio real de FastF1 para esta sesión.

    Estructura: {cache_dir}/{year}/{date}_{EventSlug}/{date}_{SessionName}/
    """
    year_dir = Path(cache_dir) / str(year)
    if not year_dir.exists():
        return None
    ff1_sess = _FF1_SESSION_NAMES.get(session_type, session_type)
    evt_slug = re.sub(r"[^\w]", "_", event_name).lower()
    for event_dir in year_dir.iterdir():
        if not event_dir.is_dir():
            continue
        if evt_slug in event_dir.name.lower():
            for session_dir in event_dir.iterdir():
                if session_dir.is_dir() and session_dir.name.endswith("_" + ff1_sess):
                    return session_dir
    return None


def upload_session_cache(year: int, event_name: str, session_type: str, cache_dir: str) -> int:
    """Sube los archivos de cache de FastF1 de una sesión a R2. Retorna cantidad subida.

    La clave R2 es: fastf1-cache/{path_relativo_desde_cache_dir}
    Preserva el path exacto para que download reconstruya la estructura correcta.
    """
    client = _get_client()
    if client is None:
        return 0
    session_dir = _local_session_dir(year, event_name, session_type, cache_dir)
    if session_dir is None:
        _log.warning("r2 | local cache dir not found | %s %s %s", year, event_name, session_type)
        return 0
    cache_path = Path(cache_dir)
    uploaded   = 0
    for f in session_dir.rglob("*"):
        if not f.is_file():
            continue
        rel = str(f.relative_to(cache_path)).replace("\\", "/")
        key = f"fastf1-cache/{rel}"
        try:
            client.upload_file(str(f), _BUCKET, key)
            uploaded += 1
        except Exception as e:
            _log.warning("r2 | upload failed | file=%s | %s", f.name, e)
    return uploaded


def download_session_cache(year: int, event_name: str, session_type: str, cache_dir: str) -> bool:
    """Baja los archivos de cache de FastF1 desde R2. Retorna True si encontró archivos.

    Lista objetos bajo fastf1-cache/{year}/ y filtra por event slug + session name.
    """
    client = _get_client()
    if client is None:
        return False
    ff1_sess   = _FF1_SESSION_NAMES.get(session_type, session_type)
    evt_slug   = re.sub(r"[^\w]", "_", event_name).lower()
    year_prefix = f"fastf1-cache/{year}/"
    try:
        resp = client.list_objects_v2(Bucket=_BUCKET, Prefix=year_prefix)
    except Exception as e:
        _log.warning("r2 | list_objects failed | %s", e)
        return False
    objects  = resp.get("Contents", [])
    matching = [
        obj for obj in objects
        if evt_slug in obj["Key"].lower()
        and f"_{ff1_sess}/" in obj["Key"]
    ]
    if not matching:
        return False
    cache_path = Path(cache_dir)
    downloaded = 0
    for obj in matching:
        key   = obj["Key"]
        rel   = key[len("fastf1-cache/"):]
        local = cache_path / rel
        local.parent.mkdir(parents=True, exist_ok=True)
        try:
            client.download_file(_BUCKET, key, str(local))
            downloaded += 1
        except Exception as e:
            _log.warning("r2 | download failed | key=%s | %s", key, e)
    return downloaded > 0
