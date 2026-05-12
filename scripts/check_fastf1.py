# Utilidad de exploración — verifica que FastF1 cargue datos de clasificación correctamente.
import fastf1
import pandas as pd

# Enable cache
fastf1.Cache.enable_cache("data/raw")

try:
    print("Intentando cargar la sesión de clasificación (Q) para Miami 2024...")
    session = fastf1.get_session(2024, "Miami", "Q")
    session.load(laps=True, telemetry=False) # Solo cargamos lo básico para no tardar

    print(f"Sesión: {session.name}")
    print(f"¿Hay vueltas cargadas?: {len(session.laps) > 0}")
    if len(session.laps) > 0:
        print("Columnas disponibles en las vueltas:")
        print(session.laps.columns.tolist())
        # Verificamos si hay una sola vuelta con datos de sectores
        sample_lap = session.laps.iloc[0]
        print(f"Muestra S1: {sample_lap["Sector1Time"]}, S2: {sample_lap["Sector2Time"]}")
    else:
        print("No se encontraron vueltas en la sesión de clasificación.")
except Exception as e:
    print(f"Error al cargar la sesión: {e}")