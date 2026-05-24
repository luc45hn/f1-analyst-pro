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
    ("sessions_load_summary", ""),
    ("sessions_db_status", {}),
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
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("""
            <div style="text-align:center;padding:2rem 0 2rem 0;">
                <div style="width:48px;height:48px;background:#E24B4A;border-radius:10px;
                            display:inline-flex;align-items:center;justify-content:center;
                            font-size:20px;font-weight:600;color:white;margin-bottom:16px;">F1</div>
                <div style="font-size:22px;font-weight:500;margin-bottom:6px;">F1 Analyst Pro</div>
                <div style="font-size:13px;color:#666;">
                    Análisis técnico de telemetría · Temporada 2026
                </div>
            </div>
        """, unsafe_allow_html=True)

        with st.form("login_form"):
            email     = st.text_input("Email")
            password  = st.text_input("Contraseña", type="password")
            submitted = st.form_submit_button("Iniciar sesión", use_container_width=True)
            st.markdown(
                '<div style="text-align:center;font-size:11px;color:#444;padding-top:8px;">'
                'Acceso restringido · Solo usuarios autorizados</div>',
                unsafe_allow_html=True,
            )

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
    st.markdown("""
        <div style="padding: 0.5rem 0 1rem 0;">
            <div style="display:flex; align-items:center; gap:10px; margin-bottom:4px;">
                <div style="width:28px;height:28px;background:#E24B4A;border-radius:6px;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:600;color:white;flex-shrink:0;">F1</div>
                <span style="font-size:1.25rem; font-weight:700; letter-spacing:0.5px;">F1 Analyst Pro</span>
            </div>
            <div style="color:#888; font-size:0.78rem; padding-left:2px; letter-spacing:1px;">
                TEMPORADA {year}
            </div>
        </div>
        <hr style="border:none; border-top:1px solid #2a2a2a; margin:0 0 1rem 0;">
    """.format(year=st.session_state.year), unsafe_allow_html=True)

    gp_input = st.text_input("Gran Premio", placeholder="ej: Miami, Monaco, Australia...")
    load_btn = st.button("Cargar GP", type="primary", use_container_width=True)

    if load_btn and gp_input.strip():
        try:
            gp_name, year = parse_gp_input(gp_input)
            db = F1Database()
            with st.spinner("⏳ Descargando telemetría..."):
                ok, n_loaded, n_total = ensure_sessions_loaded(gp_name, db, year)
            if ok:
                st.session_state.gp_loaded = gp_name
                st.session_state.year = year
                st.session_state.compare_previous_year = False
                st.session_state.weekend_type = detect_weekend_type(gp_name, year)
                st.session_state.agent = F1ConsultantAgent()
                st.session_state.messages = []
                st.session_state.load_status = "ok"
                st.session_state.sessions_available = get_session_display_names(gp_name, year)
                st.session_state.sessions_load_summary = f"{n_loaded} de {n_total}"
                st.session_state.sessions_db_status = {
                    code: db.session_exists(year, gp_name, code)
                    for code, _ in st.session_state.sessions_available
                }
            else:
                st.session_state.load_status = "error"
                st.session_state.gp_loaded = None
                st.session_state.year = DEFAULT_YEAR
        except Exception:
            _log.exception("GP load failed | input=%r", gp_input)
            st.session_state.load_status = "error"
            st.session_state.gp_loaded = None
            st.session_state.year = DEFAULT_YEAR

    if st.session_state.load_status == "error":
        st.error("❌ No se pudo cargar el GP. Verificá el nombre.")

    if st.session_state.gp_loaded:
        wtype = st.session_state.weekend_type
        badge = "🏃 Sprint" if wtype == "sprint" else "📅 Normal"
        st.success(f"✅ **{st.session_state.gp_loaded} {st.session_state.year}** — {st.session_state.sessions_load_summary} sesiones")
        st.caption(f"Formato: {badge}")
        st.divider()

        st.markdown(
            '<p style="color:#888;font-size:0.72rem;font-weight:600;letter-spacing:1px;margin:0 0 8px 2px;">ANÁLISIS RÁPIDOS</p>',
            unsafe_allow_html=True,
        )

        _categories = [
            ("GENERAL", [
                ("Resumen del fin de semana",          "Resumen del fin de semana"),
                ("Batalla entre compañeros de equipo", "Batalla entre compañeros de equipo"),
            ]),
            ("CLASIFICACIÓN", [
                ("Comparativa de clasificación", "Comparativa de clasificación"),
                ("Análisis por sectores",        "Análisis por sectores"),
            ]),
            ("CARRERA", [
                ("Ritmo de carrera por piloto", "Ritmo de carrera por piloto"),
                ("Degradación de neumáticos",   "Degradación de neumáticos"),
                ("Análisis de pit stops",       "Análisis de pit stops"),
                ("Undercut / Overcut",          "Undercut / Overcut"),
            ]),
        ]
        if st.session_state.weekend_type == "sprint":
            _categories.append(("SPRINT", [
                ("Análisis Sprint Race",                     "Análisis Sprint Race"),
                ("Comparativa SQ vs Q (ritmo una vuelta)",   "Comparativa SQ vs Q (ritmo una vuelta)"),
            ]))

        for cat_label, items in _categories:
            st.markdown(
                f'<p style="color:#555;font-size:0.68rem;font-weight:600;letter-spacing:1px;margin:10px 0 4px 2px;">{cat_label}</p>',
                unsafe_allow_html=True,
            )
            for btn_label, prompt in items:
                if st.button(btn_label, use_container_width=True, key=f"btn_{prompt}"):
                    st.session_state.pending_prompt = prompt
                    st.rerun()

        st.divider()
        if not st.session_state.compare_previous_year:
            if st.button("📅 Comparar con año anterior", use_container_width=True, key="btn_compare"):
                st.session_state.pending_compare = True
                st.rerun()
        else:
            st.caption(f"✅ Comparando {st.session_state.year - 1} vs {st.session_state.year}")

    st.markdown(
        '<hr style="border:none;border-top:1px solid #2a2a2a;margin:1.5rem 0 0.5rem 0;">',
        unsafe_allow_html=True,
    )
    _user_email = st.session_state.supabase_session.user.email
    st.markdown(
        f'<div style="color:#555;font-size:0.68rem;letter-spacing:0.5px;padding:0 2px 6px 2px;'
        f'white-space:nowrap;overflow:hidden;text-overflow:ellipsis;" title="{_user_email}">'
        f'👤 {_user_email}</div>',
        unsafe_allow_html=True,
    )
    if st.button("Cerrar sesión", use_container_width=True, key="btn_logout"):
        _sb.auth.sign_out()
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        st.rerun()

# ── Main area ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
[data-testid="stChatMessageAvatarUser"],
[data-testid="stChatMessageAvatarAssistant"] {
    width: 24px !important;
    height: 24px !important;
    font-size: 12px !important;
    border-radius: 4px !important;
}
</style>
""", unsafe_allow_html=True)
if st.session_state.gp_loaded:
    wtype        = st.session_state.weekend_type
    format_codes = ["FP1", "SQ", "SS", "Q", "R"] if wtype == "sprint" else ["FP1", "FP2", "FP3", "Q", "R"]
    _db_status = st.session_state.sessions_db_status
    pills_html = ""
    for code in format_codes:
        if _db_status.get(code, False):
            pills_html += (
                f'<span style="background:#2D6A4F;color:#52B788;border:1px solid #3a8a65;'
                f'border-radius:4px;padding:2px 9px;font-size:0.7rem;font-weight:700;'
                f'letter-spacing:0.5px;">{code}</span>'
            )
        else:
            pills_html += (
                f'<span style="background:var(--color-background-secondary);'
                f'color:var(--color-text-tertiary);border:1px solid transparent;'
                f'border-radius:4px;padding:2px 9px;font-size:0.7rem;font-weight:700;'
                f'letter-spacing:0.5px;opacity:0.5;">{code}</span>'
            )
    format_badge = (
        '<span style="background:#2a1a0a;color:#fb923c;border:1px solid #4a2a0a;'
        'border-radius:4px;padding:2px 9px;font-size:0.7rem;font-weight:700;letter-spacing:1px;">SPRINT</span>'
        if wtype == "sprint" else
        '<span style="background:#0f1a2a;color:#60a5fa;border:1px solid #1a2e4a;'
        'border-radius:4px;padding:2px 9px;font-size:0.7rem;font-weight:700;letter-spacing:1px;">NORMAL</span>'
    )
    st.markdown(
        f'<div style="padding:1.25rem 0 1.25rem 0;border-bottom:1px solid #1e1e1e;margin-bottom:1.5rem;">'
        f'<div style="color:#555;font-size:0.68rem;font-weight:600;letter-spacing:2px;margin-bottom:6px;">GRAN PREMIO</div>'
        f'<div style="font-size:2rem;font-weight:800;line-height:1.1;margin-bottom:12px;">{st.session_state.gp_loaded} <span style="color:#333;font-size:1.1rem;font-weight:400;">{st.session_state.year}</span></div>'
        f'<div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">'
        f'{format_badge}'
        f'<span style="color:#2a2a2a;">|</span>'
        f'<div style="display:flex;gap:4px;">{pills_html}</div>'
        f'</div></div>',
        unsafe_allow_html=True,
    )
else:
    st.markdown(
        '<h2 style="font-weight:800;letter-spacing:-0.5px;margin-bottom:1.5rem;">Consultor Técnico F1</h2>',
        unsafe_allow_html=True,
    )

if not st.session_state.gp_loaded:
    st.info("👈 Ingresá el nombre de un Gran Premio en el panel izquierdo para comenzar.")
    st.stop()

# Render chat history
for i, msg in enumerate(st.session_state.messages):
    if msg["role"] == "system":
        st.markdown(
            f'<div style="text-align:center;color:#444;font-size:0.78rem;'
            f'padding:6px 12px;margin:4px 0;">— {msg["content"]} —</div>',
            unsafe_allow_html=True,
        )
    else:
        _avatar = "📊" if msg["role"] == "assistant" else "🎙️"
        with st.chat_message(msg["role"], avatar=_avatar):
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
        ok, n_loaded, n_total = ensure_sessions_loaded(gp_name, db, prev_year)
    if ok:
        st.session_state.compare_previous_year = True
        sys_msg = (
            f"Datos de **{gp_name} {prev_year}** cargados ({n_loaded} de {n_total} sesiones). "
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
    with st.chat_message("user", avatar="🎙️"):
        st.markdown(prompt_to_send)

    with st.chat_message("assistant", avatar="📊"):
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
            _is_overloaded = (
                "529" in str(e) or "overloaded_error" in str(e).lower()
                or (hasattr(e, "status_code") and e.status_code == 529)
            )
            if _is_overloaded:
                error_msg = "⏳ El servicio está temporalmente saturado. Esperá unos segundos y volvé a intentar la misma pregunta."
                st.warning(error_msg)
            else:
                error_msg = f"Error al procesar la consulta: {e}"
                st.error(error_msg)
            st.session_state.messages.append({"role": "assistant", "content": error_msg})
