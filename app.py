import streamlit as st
from core.consultant_agent import F1ConsultantAgent
from core.database_manager import F1Database
from core.weekend_detector import detect_weekend_type, ensure_sessions_loaded, get_session_display_names
from core.config import PREDEFINED_ANALYSES
from core.gp_resolver import parse_gp_input, DEFAULT_YEAR


# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="F1 Analyst Pro",
    page_icon="🏎️",
    layout="wide",
)

# ── Session state ─────────────────────────────────────────────────────────────
for key, default in [
    ("messages", []),
    ("gp_loaded", None),
    ("weekend_type", None),
    ("agent", None),
    ("pending_prompt", None),
    ("load_status", None),
    ("sessions_available", []),
    ("year", DEFAULT_YEAR),
]:
    if key not in st.session_state:
        st.session_state[key] = default

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("🏎️ F1 Analyst Pro")
    st.caption(f"Temporada {st.session_state.year}")
    st.divider()

    gp_input = st.text_input("Gran Premio", placeholder="ej: Miami, Monaco, Australia...")
    load_btn = st.button("Cargar GP", type="primary", use_container_width=True)

    if load_btn and gp_input.strip():
        gp_name, year = parse_gp_input(gp_input)
        db = F1Database()
        with st.spinner("⏳ Descargando telemetría..."):
            ok = ensure_sessions_loaded(gp_name, db, year)
        if ok:
            st.session_state.gp_loaded = gp_name
            st.session_state.year = year
            st.session_state.weekend_type = detect_weekend_type(gp_name)
            st.session_state.agent = F1ConsultantAgent()
            st.session_state.messages = []
            st.session_state.load_status = "ok"
            st.session_state.sessions_available = get_session_display_names(gp_name)
        else:
            st.session_state.load_status = "error"
            st.session_state.gp_loaded = None
            st.session_state.year = DEFAULT_YEAR

    if st.session_state.load_status == "error":
        st.error("❌ No se pudo cargar el GP. Verificá el nombre.")

    if st.session_state.gp_loaded:
        wtype = st.session_state.weekend_type
        badge = "🏃 Sprint" if wtype == "sprint" else "📅 Normal"
        st.success(f"✅ **{st.session_state.gp_loaded}**")
        st.caption(f"Formato: {badge}")
        st.divider()

        st.markdown("**Análisis rápidos**")
        analyses = list(PREDEFINED_ANALYSES)
        if st.session_state.weekend_type == "sprint":
            analyses += ["Análisis Sprint Race", "Comparativa SQ vs Q (ritmo una vuelta)"]
        for analysis in analyses:
            if st.button(analysis, use_container_width=True, key=f"btn_{analysis}"):
                st.session_state.pending_prompt = analysis
                st.rerun()

# ── Main area ─────────────────────────────────────────────────────────────────
st.markdown("## Consultor Técnico F1")

if st.session_state.gp_loaded:
    wtype = st.session_state.weekend_type
    label = "SPRINT 🏃" if wtype == "sprint" else "NORMAL 📅"
    sessions_str = " · ".join(name for _, name in st.session_state.sessions_available)
    st.info(f"🏁 Fin de semana **{label}** — Sesiones disponibles: {sessions_str}")

if not st.session_state.gp_loaded:
    st.info("👈 Ingresá el nombre de un Gran Premio en el panel izquierdo para comenzar.")
    st.stop()

# Render chat history
for i, msg in enumerate(st.session_state.messages):
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg["role"] == "assistant" and msg.get("chart") is not None:
            st.plotly_chart(msg["chart"], use_container_width=True, key=f"chart_{i}")

# Resolve prompt source (sidebar button or chat input)
prompt_to_send = None
if st.session_state.pending_prompt:
    prompt_to_send = st.session_state.pending_prompt
    st.session_state.pending_prompt = None

if chat_input := st.chat_input("Hacé una pregunta sobre el GP..."):
    prompt_to_send = chat_input

# Process
if prompt_to_send:
    st.session_state.messages.append({"role": "user", "content": prompt_to_send})
    with st.chat_message("user"):
        st.markdown(prompt_to_send)

    with st.chat_message("assistant"):
        try:
            with st.spinner("Analizando datos..."):
                result = st.session_state.agent.send_message(
                    prompt_to_send,
                    st.session_state.gp_loaded,
                    st.session_state.year,
                )
            st.markdown(result["text"])
            if result["chart"] is not None:
                st.plotly_chart(result["chart"], use_container_width=True, key=f"chart_{len(st.session_state.messages)}")
            st.session_state.messages.append({"role": "assistant", "content": result["text"], "chart": result["chart"]})
        except Exception as e:
            error_msg = f"Error al procesar la consulta: {e}"
            st.error(error_msg)
            st.session_state.messages.append({"role": "assistant", "content": error_msg})
