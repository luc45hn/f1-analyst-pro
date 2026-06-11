import re
import time
import streamlit as st
from streamlit_local_storage import LocalStorage
from supabase import create_client
from core.consultant_agent import F1ConsultantAgent
from core.export_manager import export_to_docx, export_to_pdf
from core.database_manager import F1Database
from core.weekend_detector import detect_weekend_type, ensure_sessions_loaded, get_session_display_names, _get_event, _get_sessions
from core.config import PREDEFINED_ANALYSES, SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY, APP_VERSION, DAILY_COST_LIMIT_USD
from core.gp_resolver import parse_gp_input, DEFAULT_YEAR, GPNotFoundError
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
    ("session_expired", False),
    ("messages", []),
    ("gp_loaded", None),
    ("loading_gp", False),
    ("_pending_gp_name", None),
    ("_pending_gp_year", DEFAULT_YEAR),
    ("_pending_gp_input_raw", ""),
    ("weekend_type", None),
    ("agent", None),
    ("pending_prompt", None),
    ("load_status", None),
    ("load_error_gp", ""),
    ("load_error_year", DEFAULT_YEAR),
    ("sessions_available", []),
    ("year", DEFAULT_YEAR),
    ("compare_previous_year", False),
    ("pending_compare", False),
    ("sessions_load_summary", ""),
    ("sessions_db_status", {}),
    ("gp_input_raw", ""),
    ("gp_display", None),
    ("gp_notes", []),
]:
    if key not in st.session_state:
        st.session_state[key] = default

# ── Auth gate ─────────────────────────────────────────────────────────────────
_sb = create_client(SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY)
local_storage = LocalStorage()

# logged_out flag: limpiar localStorage y rerun antes de mostrar el form
if st.session_state.get("logged_out"):
    del st.session_state["logged_out"]
    local_storage.deleteItem("f1_session")
    st.rerun()

# Restaurar sesión desde localStorage si no está en session_state
if not st.session_state.supabase_session:
    try:
        _stored = local_storage.getItem("f1_session")
        if _stored and isinstance(_stored, dict):
            _at = _stored.get("access_token")
            _rt = _stored.get("refresh_token")
            if _at and _rt:
                _resp = _sb.auth.set_session(_at, _rt)
                if _resp.session:
                    st.session_state.supabase_session = _resp.session
    except Exception:
        _log.warning("No se pudo restaurar sesión desde localStorage")

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

        if st.session_state.session_expired:
            st.warning("⏱️ Tu sesión expiró. Ingresá nuevamente para continuar.")

        with st.form("login_form"):
            email     = st.text_input("Email")
            password  = st.text_input("Contraseña", type="password")
            submitted = st.form_submit_button("Iniciar sesión", width="stretch")
            st.markdown(
                '<div style="text-align:center;font-size:11px;color:#444;padding-top:8px;">'
                'Acceso restringido · Solo usuarios autorizados</div>',
                unsafe_allow_html=True,
            )

        if submitted:
            try:
                resp = _sb.auth.sign_in_with_password({"email": email, "password": password})
                st.session_state.supabase_session = resp.session
                local_storage.setItem("f1_session", {
                    "access_token": resp.session.access_token,
                    "refresh_token": resp.session.refresh_token,
                })
                st.session_state.auth_error = None
                st.session_state.session_expired = False
                _log.info("login success | email=%s", email)
                st.rerun()
            except Exception as e:
                _log.warning("login failed | email=%s error=%s", email, e)
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

    gp_input = st.text_input("Gran Premio", placeholder="ej: Canada, Suzuka, Monaco...")
    st.markdown(
        '<div style="font-size: 11px; color: var(--color-text-tertiary); margin-bottom: 8px;">'
        'Escribí el nombre en español o inglés. Podés incluir el año: \'Canada 2025\''
        '</div>',
        unsafe_allow_html=True,
    )
    load_btn = st.button("Cargar GP", type="primary", width="stretch")

    if load_btn and gp_input.strip():
        gp_name, year = gp_input.strip(), DEFAULT_YEAR  # fallback para mensajes de error
        try:
            gp_name, year = parse_gp_input(gp_input)
            st.session_state._pending_gp_name = gp_name
            st.session_state._pending_gp_year = year
            st.session_state._pending_gp_input_raw = gp_input.strip()
            st.session_state.loading_gp = True
            st.rerun()
        except GPNotFoundError:
            _log.warning("GP not found | input=%r", gp_input)
            st.session_state.load_status = "not_found"
            st.session_state.load_error_gp = gp_name
            st.session_state.load_error_year = year
            st.session_state.gp_loaded = None
            st.session_state.gp_display = None
            st.session_state.year = DEFAULT_YEAR

    _ls = st.session_state.load_status
    if _ls in ("not_found", "no_data"):
        _eg = st.session_state.load_error_gp
        _ey = st.session_state.load_error_year
        st.error(
            f'❌ No se encontraron datos para "{_eg}" {_ey}. Verificá el nombre del GP — '
            'probá con el nombre completo en inglés (ej: "Canadian Grand Prix") '
            'o revisá si el evento ya ocurrió.'
        )
    elif _ls == "connection_error":
        st.error("❌ Error de conexión. Verificá tu conexión a internet e intentá nuevamente.")
    elif _ls == "error":
        st.error("❌ No se pudo cargar el GP. Verificá el nombre.")

    if st.session_state.gp_loaded:
        wtype = st.session_state.weekend_type
        badge = "🏃 Sprint" if wtype == "sprint" else "📅 Normal"
        st.success(f"✅ **{st.session_state.gp_display} {st.session_state.year}** — {st.session_state.sessions_load_summary} sesiones")
        _raw_name = re.sub(r'\b20\d{2}\b', '', st.session_state.gp_input_raw).strip()
        if _raw_name.lower() != st.session_state.gp_display.lower():
            st.caption(f"Nombre interpretado como: **{st.session_state.gp_display}**")
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
                if st.button(btn_label, width="stretch", key=f"btn_{prompt}"):
                    st.session_state.pending_prompt = prompt
                    st.rerun()

        st.divider()
        if not st.session_state.compare_previous_year:
            if st.button("📅 Comparar con año anterior", width="stretch", key="btn_compare"):
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
    try:
        from datetime import date as _date
        _cost_db = F1Database()
        _daily_cost = _cost_db.get_daily_cost(_user_email, _date.today())
        st.markdown(
            f'<div style="font-size:10px;color:var(--color-text-tertiary);margin-top:2px;padding:0 2px 4px 2px;">'
            f'Uso hoy: ${_daily_cost:.2f} / ${DAILY_COST_LIMIT_USD:.2f}</div>',
            unsafe_allow_html=True,
        )
    except Exception:
        pass
    st.markdown(
        f'<div style="font-size:10px;color:var(--color-text-tertiary);margin-top:4px;">v{APP_VERSION}</div>',
        unsafe_allow_html=True,
    )
    if st.button("Cerrar sesión", width="stretch", key="btn_logout"):
        _log.info("logout | email=%s", _user_email)
        try:
            _sb.auth.sign_out()
        except Exception:
            pass
        local_storage.deleteItem("f1_session")
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        st.session_state["logged_out"] = True
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
if st.session_state.loading_gp:
    _loading_ph = st.empty()
    _gp_name = st.session_state._pending_gp_name
    _year    = st.session_state._pending_gp_year
    try:
        _n_sessions = len(_get_sessions(_gp_name, _year))
    except Exception:
        _n_sessions = 5
    _spinner_msg = (
        f"⏳ Descargando {_n_sessions} sesiones de {_gp_name}... "
        f"(puede tardar hasta {_n_sessions * 15}s la primera vez)"
    )
    with _loading_ph.container():
        with st.spinner(_spinner_msg):
            try:
                db = F1Database()
                _t0_load = time.time()
                ok, n_loaded, n_total = ensure_sessions_loaded(_gp_name, db, _year)
                if ok:
                    _log.info("GP loaded | gp=%s year=%d sessions=%d/%d elapsed=%.1fs",
                              _gp_name, _year, n_loaded, n_total, time.time() - _t0_load)
                    _official = _get_event(_year, _gp_name).get("EventName", "").strip() or _gp_name
                    st.session_state.gp_loaded            = _gp_name
                    st.session_state.gp_display           = _official
                    st.session_state.gp_input_raw         = st.session_state._pending_gp_input_raw
                    st.session_state.year                 = _year
                    st.session_state.compare_previous_year = False
                    st.session_state.weekend_type         = detect_weekend_type(_gp_name, _year)
                    st.session_state.agent                = F1ConsultantAgent()
                    st.session_state.messages             = []
                    st.session_state.gp_notes             = []
                    st.session_state.load_status          = "ok"
                    st.session_state.sessions_available   = get_session_display_names(_gp_name, _year)
                    st.session_state.sessions_load_summary = f"{n_loaded} de {n_total}"
                    st.session_state.sessions_db_status   = {
                        code: db.session_exists(_year, _gp_name, code)
                        for code, _ in st.session_state.sessions_available
                    }
                    st.session_state.loading_gp = False
                else:
                    st.session_state.load_status     = "no_data"
                    st.session_state.load_error_gp   = _gp_name
                    st.session_state.load_error_year = _year
                    st.session_state.gp_loaded       = None
                    st.session_state.gp_display      = None
                    st.session_state.year            = DEFAULT_YEAR
                    st.session_state.loading_gp      = False
            except (ConnectionError, TimeoutError, OSError):
                _log.exception("GP load connection error | gp=%r year=%d", _gp_name, _year)
                st.session_state.load_status  = "connection_error"
                st.session_state.gp_loaded    = None
                st.session_state.gp_display   = None
                st.session_state.year         = DEFAULT_YEAR
                st.session_state.loading_gp   = False
            except Exception:
                _log.exception("GP load failed | gp=%r year=%d", _gp_name, _year)
                st.session_state.load_status  = "error"
                st.session_state.gp_loaded    = None
                st.session_state.gp_display   = None
                st.session_state.year         = DEFAULT_YEAR
                st.session_state.loading_gp   = False
    st.rerun()
elif st.session_state.gp_loaded:
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
        f'<div style="font-size:2rem;font-weight:800;line-height:1.1;margin-bottom:12px;">{st.session_state.gp_display} <span style="color:#333;font-size:1.1rem;font-weight:400;">{st.session_state.year}</span></div>'
        f'<div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">'
        f'{format_badge}'
        f'<span style="color:#2a2a2a;">|</span>'
        f'<div style="display:flex;gap:4px;">{pills_html}</div>'
        f'</div></div>',
        unsafe_allow_html=True,
    )

    _gp_label = st.session_state.gp_display or st.session_state.gp_loaded
    with st.expander("💡 ¿Cómo usar F1 Analyst Pro?", expanded=False):
        st.markdown("#### Ejemplos de preguntas")
        if wtype == "sprint":
            _q1 = f"¿Cómo le fue a [piloto] en la Sprint Qualifying en {_gp_label}?"
            _q4 = "Mostrame la telemetría de [piloto] en la Sprint Qualifying"
        else:
            _q1 = f"¿Cuál fue la pole y por cuánto en {_gp_label}?"
            _q4 = "Mostrame la telemetría de [piloto] en la clasificación"
        st.markdown(f"""
- {_q1}
- Comparame el ritmo de carrera de los dos [equipo]
- ¿Qué estrategia usaron los top 5 en carrera?
- {_q4}
""")
        st.markdown("#### Tips")
        st.markdown("""
- Usá nombres completos o códigos de 3 letras: ej. Colapinto o COL
- Para telemetría mencioná la sesión: telemetría de COL en la Sprint Qualifying
- Podés comparar con el año anterior usando el botón de abajo en el panel
- Podés agregar contexto escribiendo: "Nota: Mercedes trajo fondo plano nuevo a este GP"
""")
        st.markdown("#### Capacidades")
        _col_yes, _col_no = st.columns(2)
        with _col_yes:
            st.markdown("""**✅ Puede hacer**
- Clasificación
- Carrera
- Estrategias
- Telemetría
- Comparativas entre años""")
        with _col_no:
            st.markdown("""**❌ No puede hacer**
- Datos en tiempo real
- Predicciones
- Info fuera de la sesión""")

else:
    st.markdown("""
        <div style="padding: 3rem 0 2rem 0; max-width: 700px;">
            <div style="font-size: 2.5rem; font-weight: 800; letter-spacing: -1px; margin-bottom: 0.75rem;">
                Bienvenido a F1 Analyst Pro
            </div>
            <div style="font-size: 1rem; color: var(--color-text-secondary); margin-bottom: 2rem; line-height: 1.6;">
                Tu asistente de análisis técnico de Fórmula 1. Analizá telemetría, ritmos de carrera,
                estrategias de pit stop y mucho más — en lenguaje natural.
            </div>
            <div style="font-size: 0.8rem; font-weight: 600; letter-spacing: 1.5px; color: #555; margin-bottom: 1rem;">
                EJEMPLOS DE PREGUNTAS
            </div>
            <ul style="list-style: none; padding: 0; margin: 0 0 2rem 0; display: flex; flex-direction: column; gap: 8px;">
                <li style="background: var(--color-background-secondary); border: 1px solid #222; border-radius: 8px; padding: 10px 14px; font-size: 0.88rem; color: var(--color-text-secondary);">
                    💬 &ldquo;¿Quién tuvo mejor ritmo en la carrera, Verstappen o Hamilton?&rdquo;
                </li>
                <li style="background: var(--color-background-secondary); border: 1px solid #222; border-radius: 8px; padding: 10px 14px; font-size: 0.88rem; color: var(--color-text-secondary);">
                    💬 &ldquo;Mostrá la comparativa de sectores en clasificación&rdquo;
                </li>
                <li style="background: var(--color-background-secondary); border: 1px solid #222; border-radius: 8px; padding: 10px 14px; font-size: 0.88rem; color: var(--color-text-secondary);">
                    💬 &ldquo;¿Cómo fue la degradación de neumáticos en el stint largo de Ferrari?&rdquo;
                </li>
                <li style="background: var(--color-background-secondary); border: 1px solid #222; border-radius: 8px; padding: 10px 14px; font-size: 0.88rem; color: var(--color-text-secondary);">
                    💬 &ldquo;¿Qué equipos ganaron posiciones con los pit stops?&rdquo;
                </li>
            </ul>
            <div style="background: #0f1a2a; border: 1px solid #1a2e4a; border-radius: 10px; padding: 14px 18px; display: flex; align-items: center; gap: 12px;">
                <div style="font-size: 1.4rem;">👈</div>
                <div style="font-size: 0.88rem; color: #60a5fa; line-height: 1.5;">
                    Escribí el nombre de un GP en el panel izquierdo y hacé click en <strong>Cargar GP</strong>
                </div>
            </div>
        </div>
    """, unsafe_allow_html=True)
    st.stop()

# Render chat history
_last_asst_idx = max(
    (j for j, m in enumerate(st.session_state.messages) if m["role"] == "assistant"),
    default=-1,
)
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
                st.plotly_chart(msg["chart"], width="stretch", key=f"chart_{i}")
            if msg["role"] == "assistant" and i == _last_asst_idx and st.session_state.gp_loaded:
                _exp_msgs = []
                if i > 0 and st.session_state.messages[i - 1]["role"] == "user":
                    _exp_msgs.append(st.session_state.messages[i - 1])
                _exp_msgs.append(msg)
                _gp_ex = st.session_state.gp_display or st.session_state.gp_loaded
                _yr_ex = st.session_state.year
                _fname = f"analisis_{_gp_ex.replace(' ', '_')}_{_yr_ex}"
                with st.expander("🗂️ Descargar análisis", expanded=False):
                    _c1, _c2 = st.columns(2)
                    with _c1:
                        st.download_button("📄 DOCX",
                            data=export_to_docx(_exp_msgs, _gp_ex, _yr_ex),
                            file_name=f"{_fname}.docx",
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            key=f"exp_docx_{i}")
                    with _c2:
                        st.download_button("📄 PDF",
                            data=export_to_pdf(_exp_msgs, _gp_ex, _yr_ex),
                            file_name=f"{_fname}.pdf",
                            mime="application/pdf",
                            key=f"exp_pdf_{i}")

# Handle comparison data loading
if st.session_state.pending_compare:
    st.session_state.pending_compare = False
    gp_name = st.session_state.gp_loaded
    gp_display = st.session_state.gp_display or gp_name
    prev_year = st.session_state.year - 1
    db = F1Database()
    with st.spinner(f"⏳ Cargando datos de {gp_display} {prev_year}..."):
        ok, n_loaded, n_total = ensure_sessions_loaded(gp_name, db, prev_year)
    if ok:
        _log.info("compare activated | gp=%s prev_year=%d sessions=%d/%d",
                  gp_name, prev_year, n_loaded, n_total)
        st.session_state.compare_previous_year = True
        sys_msg = (
            f"Datos de **{gp_display} {prev_year}** cargados ({n_loaded} de {n_total} sesiones). "
            f"Podés preguntar comparativas entre {prev_year} y {st.session_state.year}."
        )
    else:
        sys_msg = f"No se encontraron datos de {gp_display} {prev_year} en FastF1."
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

    if prompt_to_send.strip().lower().startswith("nota:"):
        _note_content = prompt_to_send.split(":", 1)[1].strip()
        if _note_content:
            st.session_state.gp_notes.append(_note_content)
        _sys_note = f"📝 Nota guardada: \"{_note_content}\". Se incluirá en las próximas consultas."
        st.session_state.messages.append({"role": "system", "content": _sys_note})
        st.rerun()
    with st.chat_message("assistant", avatar="📊"):
        try:
            _status = st.empty()
            _status.info("🔍 Analizando datos del GP...")
            def _update_status(msg):
                _status.info(msg)
            with st.spinner("Procesando..."):
                result = st.session_state.agent.send_message(
                    prompt_to_send,
                    st.session_state.gp_loaded,
                    st.session_state.year,
                    compare_previous_year=st.session_state.compare_previous_year,
                    user_email=_user_email,
                    on_status=_update_status,
                    gp_notes=st.session_state.gp_notes,
                )
            _status.empty()
            st.markdown(result["text"])
            if result["chart"] is not None:
                st.plotly_chart(result["chart"], width="stretch", key=f"chart_{len(st.session_state.messages)}")
            if st.session_state.gp_loaded:
                _exp_new = [{"role": "user", "content": prompt_to_send},
                             {"role": "assistant", "content": result["text"]}]
                _gp_ex_n = st.session_state.gp_display or st.session_state.gp_loaded
                _yr_ex_n = st.session_state.year
                _fname_n = f"analisis_{_gp_ex_n.replace(' ', '_')}_{_yr_ex_n}"
                _new_i   = len(st.session_state.messages)
                with st.expander("🗂️ Descargar análisis", expanded=False):
                    _cn1, _cn2 = st.columns(2)
                    with _cn1:
                        st.download_button("📄 DOCX",
                            data=export_to_docx(_exp_new, _gp_ex_n, _yr_ex_n),
                            file_name=f"{_fname_n}.docx",
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            key=f"exp_docx_{_new_i}")
                    with _cn2:
                        st.download_button("📄 PDF",
                            data=export_to_pdf(_exp_new, _gp_ex_n, _yr_ex_n),
                            file_name=f"{_fname_n}.pdf",
                            mime="application/pdf",
                            key=f"exp_pdf_{_new_i}")
            st.session_state.messages.append({"role": "assistant", "content": result["text"], "chart": result["chart"]})
        except Exception as e:
            _is_overloaded = (
                "529" in str(e) or "overloaded_error" in str(e).lower()
                or (hasattr(e, "status_code") and e.status_code == 529)
            )
            _is_usage_limit = (
                hasattr(e, "status_code") and e.status_code == 400
                and "api usage limits" in str(e).lower()
            )
            if _is_overloaded:
                error_msg = "⏳ El servicio está temporalmente saturado. Esperá unos segundos y volvé a intentar la misma pregunta."
                st.warning(error_msg)
            elif _is_usage_limit:
                error_msg = "⚠️ El servicio de análisis está temporalmente no disponible. Por favor intentá más tarde."
                st.warning(error_msg)
            else:
                error_msg = f"Error al procesar la consulta: {e}"
                st.error(error_msg)
            st.session_state.messages.append({"role": "assistant", "content": error_msg})
