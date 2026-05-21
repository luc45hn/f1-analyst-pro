import time
import streamlit as st
from supabase import create_client
from core.consultant_agent import F1ConsultantAgent
from core.database_manager import F1Database
from core.weekend_detector import detect_weekend_type, ensure_sessions_loaded, get_session_display_names
from core.config import PREDEFINED_ANALYSES, SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY
from core.gp_resolver import parse_gp_input, DEFAULT_YEAR
from core.logger import get_logger

_log = get_logger(__name__)


# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="F1 Analyst Pro",
    page_icon="🏎️",
    layout="wide",
)

# ── Session state ─────────────────────────────────────────────────────────────
for key, default in [
    ("supabase_session", None),
    ("auth_error", None),
    ("messages", []),
    ("gp_loaded", None),
    ("weekend_type", None),
    ("agent", None),
    ("pending_prompt", None),
    ("load_status", None),
    ("sessions_available", []),
    ("year", DEFAULT_YEAR),
    ("compare_previous_year", False),
    ("pending_compare", False),
]:
    if key not in st.session_state:
        st.session_state[key] = default

# ── Auth gate ─────────────────────────────────────────────────────────────────
_sb = create_client(SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY)

# Expire check: clear session if token has expired
if st.session_state.supabase_session:
    if st.session_state.supabase_session.expires_at < int(time.time()):
        _sb.auth.sign_out()
        st.session_state.supabase_session = None

if not st.session_state.supabase_session:
    st.markdown("## 🏎️ F1 Analyst Pro")
    with st.form("login_form"):
        email     = st.text_input("Email")
        password  = st.text_input("Contraseña", type="password")
        submitted = st.form_submit_button("Iniciar sesión", use_container_width=True)
    if submitted:
        try:
            resp = _sb.auth.sign_in_with_password({"email": email, "password": password})
            st.session_state.supabase_session = resp.session
            st.session_state.auth_error = None
            st.rerun()
        except Exception as e:
            st.session_state.auth_error = str(e)
    if st.session_state.auth_error:
        st.error(f"❌ {st.session_state.auth_error}")
    st.stop()

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
            st.session_state.compare_previous_year = False
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

        st.divider()
        if not st.session_state.compare_previous_year:
            if st.button("📅 Comparar con año anterior", use_container_width=True, key="btn_compare"):
                st.session_state.pending_compare = True
                st.rerun()
        else:
            st.caption(f"✅ Comparando {st.session_state.year - 1} vs {st.session_state.year}")

    st.divider()
    if st.button("Cerrar sesión", use_container_width=True, key="btn_logout"):
        _sb.auth.sign_out()
        for k in list(st.session_state.keys()):
            del st.session_state[k]
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
    if msg["role"] == "system":
        st.info(msg["content"])
    else:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg["role"] == "assistant" and msg.get("chart") is not None:
                st.plotly_chart(msg["chart"], use_container_width=True, key=f"chart_{i}")

# Handle comparison data loading
if st.session_state.pending_compare:
    st.session_state.pending_compare = False
    gp_name = st.session_state.gp_loaded
    prev_year = st.session_state.year - 1
    db = F1Database()
    with st.spinner(f"⏳ Cargando datos de {gp_name} {prev_year}..."):
        ok = ensure_sessions_loaded(gp_name, db, prev_year)
    if ok:
        st.session_state.compare_previous_year = True
        sys_msg = (
            f"Datos de **{gp_name} {prev_year}** cargados. "
            f"Podés preguntar comparativas entre {prev_year} y {st.session_state.year}."
        )
    else:
        sys_msg = f"No se encontraron datos de {gp_name} {prev_year} en FastF1."
    st.session_state.messages.append({"role": "system", "content": sys_msg})
    st.rerun()

# Resolve prompt source (sidebar button or chat input)
prompt_to_send = None
if st.session_state.pending_prompt:
    prompt_to_send = st.session_state.pending_prompt
    st.session_state.pending_prompt = None

if chat_input := st.chat_input("Hacé una pregunta sobre el GP..."):
    prompt_to_send = chat_input

# Process
if prompt_to_send:
    _log.info("query | gp=%s prompt_len=%d", st.session_state.gp_loaded, len(prompt_to_send))
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
                    compare_previous_year=st.session_state.compare_previous_year,
                )
            st.markdown(result["text"])
            if result["chart"] is not None:
                st.plotly_chart(result["chart"], use_container_width=True, key=f"chart_{len(st.session_state.messages)}")
            st.session_state.messages.append({"role": "assistant", "content": result["text"], "chart": result["chart"]})
        except Exception as e:
            error_msg = f"Error al procesar la consulta: {e}"
            st.error(error_msg)
            st.session_state.messages.append({"role": "assistant", "content": error_msg})
