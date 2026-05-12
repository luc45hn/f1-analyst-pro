from core.config import YEAR
from core.data_extractor import get_session_data
from core.weekend_detector import get_available_sessions, detect_weekend_type

def load_weekend(gp_name):
    weekend_type = detect_weekend_type(gp_name)
    session_types = get_available_sessions(YEAR, gp_name)
    print(f"[INFO] Formato {weekend_type} detectado para {gp_name}.")
    loaded = []
    for stype in session_types:
        print(f"[INFO] Descargando {stype}...")
        result = get_session_data(YEAR, gp_name, session_type=stype)
        if result:
            loaded.append(stype)
        else:
            print(f"[WARN] No se pudo cargar {stype} para {gp_name}.")
    return loaded

if __name__ == "__main__":
    import sys
    gp_name = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else input("Gran Premio: ").strip()
    if not gp_name:
        print("Nombre de GP vacío. Saliendo.")
        sys.exit(1)
    loaded = load_weekend(gp_name)
    if loaded:
        print(f"\n[OK] Sesiones cargadas: {', '.join(loaded)}")
    else:
        print("\n[ERROR] No se pudo cargar ninguna sesión.")
        sys.exit(1)
