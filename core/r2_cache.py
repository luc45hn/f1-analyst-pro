import os
import re
import logging
from pathlib import Path

_log = logging.getLogger(__name__)

_BUCKET = "f1-analyst-cache"

_FF1_SESSION_MAP = {
    "R":   "Race",
    "Q":   "Qualifying",
    "SS":  "Sprint",
    "SQ":  "Sprint Qualifying",
    "FP1": "Practice 1",
    "FP2": "Practice 2",
    "FP3": "Practice 3",
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


def _r2_prefix(year: int, event_name: str, session_type: str) -> str:
    return f"fastf1-cache/{year}/{event_name}/{session_type}/"


def _local_session_dir(year: int, event_name: str, session_type: str, cache_dir: str) -> Path | None:
    """Encuentra el subdirectorio de FastF1 cache para esta sesión."""
    cache_path = Path(cache_dir)
    if not cache_path.exists():
        return None
    ff1_sess = _FF1_SESSION_MAP.get(session_type, session_type)
    year_str = str(year)
    # slug para comparación sin espacios/puntuación: "Miami Grand Prix" → "miamigrandprix"
    evt_slug = re.sub(r"[^\w]", "", event_name.lower())
    for d in cache_path.iterdir():
        if not d.is_dir() or not d.name.startswith(year_str + "_"):
            continue
        if evt_slug in re.sub(r"[^\w]", "", d.name.lower()):
            session_dir = d / ff1_sess
            if session_dir.exists():
                return session_dir
    return None


def upload_session_cache(year: int, event_name: str, session_type: str, cache_dir: str) -> int:
    """Sube los archivos de cache de FastF1 de una sesión a R2. Retorna cantidad subida."""
    client = _get_client()
    if client is None:
        return 0
    session_dir = _local_session_dir(year, event_name, session_type, cache_dir)
    if session_dir is None:
        _log.warning("r2 | local cache dir not found | %s %s %s", year, event_name, session_type)
        return 0
    prefix   = _r2_prefix(year, event_name, session_type)
    uploaded = 0
    for f in session_dir.rglob("*"):
        if not f.is_file():
            continue
        rel = f.relative_to(session_dir)
        key = prefix + str(rel).replace("\\", "/")
        try:
            client.upload_file(str(f), _BUCKET, key)
            uploaded += 1
        except Exception as e:
            _log.warning("r2 | upload failed | file=%s | %s", f.name, e)
    return uploaded


def download_session_cache(year: int, event_name: str, session_type: str, cache_dir: str) -> bool:
    """Baja los archivos de cache de FastF1 desde R2. Retorna True si encontró archivos."""
    client = _get_client()
    if client is None:
        return False
    prefix = _r2_prefix(year, event_name, session_type)
    try:
        resp = client.list_objects_v2(Bucket=_BUCKET, Prefix=prefix)
    except Exception as e:
        _log.warning("r2 | list_objects failed | %s", e)
        return False
    objects = resp.get("Contents", [])
    if not objects:
        return False
    # Reconstruir bajo el directorio de sesión esperado por FastF1
    session_dir = _local_session_dir(year, event_name, session_type, cache_dir)
    if session_dir is None:
        # Directorio aún no existe localmente — crearlo con estructura esperada
        ff1_sess    = _FF1_SESSION_MAP.get(session_type, session_type)
        session_dir = Path(cache_dir) / f"{year}_{event_name}" / ff1_sess
    session_dir.mkdir(parents=True, exist_ok=True)
    downloaded = 0
    for obj in objects:
        key = obj["Key"]
        rel = key[len(prefix):]
        if not rel:
            continue
        local_path = session_dir / rel
        local_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            client.download_file(_BUCKET, key, str(local_path))
            downloaded += 1
        except Exception as e:
            _log.warning("r2 | download failed | key=%s | %s", key, e)
    return downloaded > 0
