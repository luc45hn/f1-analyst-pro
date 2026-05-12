from core.consultant_agent import F1ConsultantAgent
from core.database_manager import F1Database
from core.weekend_detector import ensure_sessions_loaded
from core.config import YEAR, PREDEFINED_ANALYSES, normalize_gp_name

MENU_OPTIONS = {str(i + 1): label for i, label in enumerate(PREDEFINED_ANALYSES)}

def show_menu():
    print("\n--- MENÚ DE ANÁLISIS ---")
    for key, label in MENU_OPTIONS.items():
        print(f"  {key:>2}. {label}")
    print("       (o escribí una pregunta directamente)")
    print('       "salir" para terminar\n')

def main():
    print(f"=== F1 ANALYST PRO — Temporada {YEAR} ===\n")
    gp_name = normalize_gp_name(input("Gran Premio (ej: Miami, Monaco): ").strip())
    if not gp_name:
        print("Nombre de GP vacío. Saliendo.")
        return

    db = F1Database()
    print(f"\nVerificando datos para {YEAR} {gp_name}...")
    if not ensure_sessions_loaded(gp_name, db):
        print("No se pudo cargar ninguna sesión. Terminando.")
        return

    consultant = F1ConsultantAgent()
    print(f"\nConsultor conectado — {gp_name} {YEAR}.")

    while True:
        show_menu()
        try:
            user_input = input("Consultor F1 > ").strip()
        except KeyboardInterrupt:
            print("\n¡Hasta luego!")
            break

        if not user_input:
            continue
        if user_input.lower() in ["salir", "exit", "quit"]:
            print("¡Hasta luego!")
            break

        prompt = MENU_OPTIONS.get(user_input, user_input)
        print("\n⏳ Procesando...\n", flush=True)
        result = consultant.send_message(prompt, gp_name)
        print(result["text"])
        print("\n" + "─" * 60)

if __name__ == "__main__":
    main()
