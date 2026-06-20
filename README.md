# F1 Analyst Pro

> An AI-powered Formula 1 telemetry analysis platform built for motorsport journalists. Ask questions in natural language and get structured, data-driven insights from official F1 timing data.

**Note:** All agent responses and the user interface are in Spanish, as the tool is designed for Spanish-speaking journalists and analysts.

[![Version](https://img.shields.io/badge/version-1.3.0-blue)](https://github.com/luc45hn/f1-analyst-pro)
[![Python](https://img.shields.io/badge/Python-3.11+-blue)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.x-red)](https://streamlit.io/)
[![Claude](https://img.shields.io/badge/Claude-Sonnet%204.6-orange)](https://anthropic.com/)
[![Supabase](https://img.shields.io/badge/Supabase-PostgreSQL-green)](https://supabase.com/)
[![Live](https://img.shields.io/badge/Live-f1--analyst.streamlit.app-brightgreen)](https://f1-analyst.streamlit.app/)

---

## Screenshots

![Welcome screen](docs/cover.png)

![GP loaded with session pills](docs/gp_loaded.png)

![Tyre degradation analysis](docs/degradation1.png)

![Tyre degradation chart](docs/degradation2.png)

![FAQ expander](docs/faqs.png)

---

## Overview

F1 Analyst Pro combines official F1 telemetry data (via FastF1) with a Retrieval-Augmented Generation (RAG) pipeline powered by Anthropic's Claude Sonnet. The system ingests lap-by-lap telemetry, stores it in a persistent PostgreSQL database, and exposes a conversational interface where a journalist can ask complex analytical questions without writing a single query.

Typical queries include:
- "Compare Colapinto vs Gasly across all sessions this weekend"
- "What was the impact of the Safety Car on tyre strategies?"
- "Compare qualifying pace between Suzuka 2025 and 2026 — what changed with the new regulations?"
- "Show me the telemetry trace for Colapinto in Sprint Qualifying"
- "Mostrame el progreso de carga mientras se descarga la telemetría de FastF1"
- "Did McLaren's undercut on Ferrari work?"
- "Show me the key moments of the race"
- "Note: Mercedes brought a new floor to this GP"

The interface includes a welcome screen with example queries for first-time users, friendly error messages, and progressive status indicators during long operations.

---

## Key Features

| Category | Capabilities |
|---|---|
| **Race analysis** | Final classification, race pace by driver, stint summary, constructor comparison |
| **Strategy** | Undercut/overcut detection with EXITOSO/FALLIDO verdict, pit stop analysis |
| **Key moments** | Automatic detection of track limits, pace anomalies (>15% off median), position drops |
| **Telemetry** | Speed/throttle/brake/gear traces per driver, Q1/Q2/Q3 segment filtering |
| **Practice sessions** | FP1/FP2/FP3 ingestion and lap time data |
| **Export** | DOCX and PDF download inline in chat after each assistant response |
| **Journalist notes** | Contextual notes via `Nota:` prefix in chat, persisted per session |
| **Year comparison** | Side-by-side analysis of the same GP across seasons |

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Presentation Layer                    │
│              app.py (Streamlit)  ·  chart_builder.py     │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│                     Agent Layer                          │
│   consultant_agent.py  ·  gp_resolver.py                 │
│   weekend_detector.py  ·  driver_resolver.py             │
│   core/config.py       ·  core/logger.py                 │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│                      Data Layer                          │
│        data_extractor.py  ·  database_manager.py         │
│                   PostgreSQL (Supabase)                  │
└──────────┬──────────────────────────────┬───────────────┘
           │                              │
┌──────────▼──────────┐     ┌─────────────▼──────────────┐
│       FastF1        │     │    Anthropic API            │
│  Official FOM data  │     │  claude-sonnet-4-6          │
│  Laps · Sectors     │     │  Reasoning · Narrative      │
│  Results · Stints   │     │  Prompt Caching enabled     │
│  Telemetry channels │     │                            │
└─────────────────────┘     └────────────────────────────┘
```

---

## Module Reference

### Presentation
| File | Responsibility |
|---|---|
| `app.py` | Streamlit UI — login screen, chat interface, sidebar menu, chart rendering, session state management |
| `core/chart_builder.py` | Plotly chart generation — lap times, sector comparisons, tyre degradation, pit stop strategy, telemetry traces |
| `core/export_manager.py` | DOCX and PDF export — formats chat responses as structured documents using python-docx and reportlab |

### Agent
| File | Responsibility |
|---|---|
| `core/consultant_agent.py` | RAG orchestrator — intent detection, context builder, Claude API calls, prompt caching, cost logging, query analytics |
| `core/gp_resolver.py` | Parses user input into `(gp_name, year)` — handles partial names, accented characters, defaults to 2026 |
| `core/weekend_detector.py` | Detects weekend format (normal vs sprint) dynamically via FastF1 — no hardcoded lists |
| `core/driver_resolver.py` | Dynamic driver name → code mapping from FastF1 — handles mid-season replacements automatically |
| `core/config.py` | Central configuration — env vars, model constants, predefined analyses list, app version |
| `core/logger.py` | Structured logging — console (INFO) + rotating file (DEBUG, 5MB × 3), token/cost metrics |

### Data
| File | Responsibility |
|---|---|
| `core/data_extractor.py` | FastF1 ingestion pipeline — extracts laps, sectors, results, stints, track status, DNF reasons |
| `core/database_manager.py` | PostgreSQL interface — all read/write operations, aggregation queries, team lineup inference, query analytics logging |
| `supabase/migrations/` | Schema versioning — SQL migration files to run manually in the Supabase SQL Editor |

---

## Technology Stack

| Layer | Technology | Purpose |
|---|---|---|
| Language | Python 3.11+ | Entire backend and frontend |
| UI Framework | Streamlit | Web interface without JS/HTML |
| LLM | Claude Sonnet 4.6 (Anthropic) | Natural language reasoning |
| F1 Data | FastF1 | Official FOM telemetry wrapper |
| Database | PostgreSQL (Supabase) | Persistent lap, results and analytics storage |
| Auth | Supabase Auth | Per-user authentication |
| Charts | Plotly | Interactive race strategy and telemetry visualizations |
| Hosting | Streamlit Cloud | Zero-infrastructure deployment |
| Testing | pytest + pytest-mock | Unit test suite |
| Version Control | GitHub | Source + schema migrations |

---

## Data Pipeline

```
FastF1 API
    │
    ▼
data_extractor.py
    │  Fetches session data (laps, results, weather)
    │  Filters: removes NaT sectors, null positions, pit-in/pit-out laps
    │  Transforms: Timedelta → float seconds, adds stint/track_status/DNF status
    │  Extended lap fields: position, is_personal_best, speed_i1/i2/fl/st, deleted, deleted_reason
    │  Weekend format detected dynamically (normal vs sprint) via FastF1
    │
    ▼
database_manager.py
    │  INSERT ... ON CONFLICT DO NOTHING (idempotent)
    │  Tables: sessions · laps · results · qualy_results · queries
    │
    ▼
PostgreSQL (Supabase)
    │  Row Level Security enabled — authenticated users only
    │
    ▼
consultant_agent.py
    │  SQL aggregation before LLM (not raw rows):
    │   · get_stint_summary()        → ~50 rows  (vs 1000 raw laps)
    │   · get_best_lap_per_driver()  → 1 row/driver
    │   · get_top_laps_per_driver()  → top 10/driver via window function
    │  Telemetry fetched on-demand from FastF1 (not stored in DB)
    │
    ▼
Claude Sonnet 4.6
    │  Prompt caching on static context (~80% token reduction on follow-up queries)
    │
    ▼
Streamlit UI
    │
    ▼
queries table (Supabase)
       Logs every query: prompt, intent, tokens, cost, user
```

---

## RAG Design

The agent uses an **intent-based context routing** strategy rather than sending all available data on every query:

- `wants_qualy` → loads Q1/Q2/Q3 or SQ best laps + results
- `wants_race` → loads stint summary + classification + best laps per driver
- `wants_sprint` → loads SS/SQ data, always includes Q for cross-session comparisons
- `wants_telemetry` → fetches car data directly from FastF1 on-demand, pre-generates Plotly chart before API call
- `is_comparative` → loads all sessions (enables prompt caching)
- `load_all` → full context with `cache_control: ephemeral` for Anthropic prompt caching

**Token optimization results:**
| Metric | Before | After |
|---|---|---|
| Input tokens (typical query) | ~36,000 | ~3–13,000 |
| Cost per query | ~$0.14 | ~$0.02–0.05 |
| Reduction | — | **~80%** |

---

## Weekend Format Support

| Format | Sessions ingested |
|---|---|
| Normal | FP1 · FP2 · FP3 · Q · R |
| Sprint | FP1 · SQ · SS · Q · R |

The system auto-detects the format dynamically via FastF1 — no hardcoded lists. Handles incomplete weekends gracefully: if a session has not taken place yet, it is skipped without error and the agent acknowledges data unavailability without assuming whether the session occurred.

---

## Telemetry Visualization

The system supports lap telemetry traces with up to 2 drivers overlaid on the same chart:

- **Speed** (km/h) — identifies braking zones, apexes, and top speed
- **Throttle** (%) — reveals full-gas phases and traction management
- **Brake** — shows braking points and intensity
- **Gear** — complements speed and braking readings

Driver names are resolved dynamically from FastF1 (e.g. "Colapinto" → `COL`), handling mid-season replacements automatically. Telemetry data is fetched on-demand from FastF1 and not stored in the database.

---

## Usage Analytics

Every query is logged to a `queries` table in Supabase with:
- User email, GP name, year, prompt text
- Intent flags (wants_qualy, wants_race, wants_sprint, wants_telemetry)
- Whether a chart was generated
- Token counts (input, output), cost in USD, elapsed time

This enables future optimization based on real usage patterns.

---

## Journalist Notes

The journalist can add contextual information that FastF1 doesn't have by typing in the chat with the `Nota:` prefix:

```
Nota: Mercedes brought a new floor to this GP
Nota: Colapinto had brake issues in FP2 according to sources
```

Notes are stored in session state, reset when loading a new GP, and automatically included in the agent context under a `NOTAS DEL PERIODISTA` section.

---

## Usage Limits

Each user has a daily cost limit of **$2.00 USD**. The limit resets at midnight.
The current daily spend is visible in the sidebar footer next to the user email.
If the limit is reached, the agent returns a friendly message without calling the API.
The limit is configurable via `DAILY_COST_LIMIT_USD` in `core/config.py`.

---

## Alternative LLM Providers

The project uses Claude Sonnet 4.6 by default, but `consultant_agent.py` can be adapted to other providers. The main change is replacing the Anthropic client with the provider's SDK.

### Google Gemini (free tier)

Gemini 2.5 Flash offers a generous free tier (1,500 requests/day, no credit card required) that covers typical usage for small teams. The trade-off is that Google may use free-tier prompts for model training.

```python
# Replace in consultant_agent.py
# From:
from anthropic import Anthropic
client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# To:
import google.generativeai as genai
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
model = genai.GenerativeModel("gemini-2.5-flash")
```

The response parsing and prompt caching logic will also need to be adapted to Gemini's API format. Quality is slightly lower than Sonnet for complex multi-session comparisons, but sufficient for standard race analysis queries.

### Local models (Ollama + LLaMA)

Running a local model via Ollama eliminates API costs entirely but requires a GPU for acceptable response times (~7s vs ~2-5min on CPU). Replace the Anthropic client with an Ollama-compatible HTTP call to `http://localhost:11434`.

---

## Testing

```bash
venv/bin/python -m pytest tests/ -v
```

| Test file | Coverage | Tests |
|---|---|---|
| `test_gp_resolver.py` | `parse_gp_input` — name parsing, year extraction, accents | 5 |
| `test_intent_detection.py` | `detect_intent` — all intent flags | 5 |
| `test_weekend_detector.py` | Format detection, session lists, fallback | 5 |
| `test_driver_resolver.py` | Name→code mapping, cache, error handling | 5 |
| `test_database_manager.py` | CRUD operations, idempotency (in-memory SQLite) | 5 |
| **Total** | | **25** |

---

## Local Development

### Prerequisites
- Python 3.11+
- A Supabase project (free tier works)
- An Anthropic API key

### Setup

```bash
git clone https://github.com/luc45hn/f1-analyst-pro.git
cd f1-analyst-pro
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Environment variables

Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

```env
ANTHROPIC_API_KEY=sk-ant-...
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_PUBLISHABLE_KEY=sb_publishable_...
SUPABASE_SECRET_KEY=sb_secret_...
SUPABASE_DB_URL=postgresql://postgres.xxx:password@pooler.supabase.com:6543/postgres
```

### Database setup

Run each migration file in order in your Supabase SQL Editor:

```bash
cat supabase/migrations/001_initial_schema.sql  # tables + RLS policies
cat supabase/migrations/002_queries_table.sql   # analytics table
```

### Run

```bash
streamlit run app.py
```

### Run tests

```bash
venv/bin/python -m pytest tests/ -v
```

---

## Deployment (Streamlit Cloud)

1. Fork or clone this repo (must be public for free tier)
2. Go to [share.streamlit.io](https://share.streamlit.io) → **New app**
3. Select the repo, branch `main`, file `app.py`
4. Under **Settings → Secrets**, add all 5 env vars in TOML format:

```toml
ANTHROPIC_API_KEY = "sk-ant-..."
SUPABASE_URL = "https://your-project.supabase.co"
SUPABASE_PUBLISHABLE_KEY = "sb_publishable_..."
SUPABASE_SECRET_KEY = "sb_secret_..."
SUPABASE_DB_URL = "postgresql://..."
```

5. Deploy — first load of each GP will re-download FastF1 cache (~30–60s). Subsequent queries are fast.

**Note:** FastF1 cache is not persistent on Streamlit Cloud and resets on each reboot. Telemetry requests on the first load of a session will take ~10s while data downloads.

---

## User Management

Users are managed via **Supabase Authentication**:
- Add users at `supabase.com/dashboard → Authentication → Users → Add user`
- The app uses email + password login
- Sessions expire automatically; users are redirected to login on expiry
- All database access is protected by Row Level Security (RLS)
- Developer toolbar options are hidden from non-admin users automatically (Streamlit `toolbarMode: auto`)

---

## Logging

Logs are written to `logs/f1_analyst.log` (excluded from git) and to the console. Each API call logs:

```
INFO [consultant_agent] API call | GP=Suzuka sessions=['Q', 'R'] input=13 output=1955 cache_write=12642 cache_read=0 cost=$0.0294 elapsed=33.98s
```

On Streamlit Cloud, logs are accessible via **Manage app → Logs** in the dashboard.

---

## Project Structure

```
f1-analyst-pro/
├── app.py                          # Streamlit entry point
├── core/
│   ├── consultant_agent.py         # RAG agent + Claude API
│   ├── chart_builder.py            # Plotly visualizations + telemetry traces
│   ├── data_extractor.py           # FastF1 ingestion
│   ├── database_manager.py         # PostgreSQL interface + query analytics
│   ├── weekend_detector.py         # Dynamic format detection via FastF1
│   ├── driver_resolver.py          # Dynamic driver name → code mapping
│   ├── gp_resolver.py              # Input parsing
│   ├── config.py                   # Central configuration + APP_VERSION
│   └── logger.py                   # Structured logging
├── tests/
│   ├── conftest.py                 # Shared fixtures (in-memory DB)
│   ├── test_gp_resolver.py
│   ├── test_intent_detection.py
│   ├── test_weekend_detector.py
│   ├── test_driver_resolver.py
│   └── test_database_manager.py
├── supabase/
│   └── migrations/
│       ├── 001_initial_schema.sql  # Core tables + RLS
│       └── 002_queries_table.sql   # Analytics table
├── .env.example                    # Environment template
├── requirements.txt
├── pytest.ini
└── .streamlit/
    └── config.toml                 # Dark theme
```

---

## Roadmap

- [x] Daily cost limit per user (configurable, default $2.00/day)
- [x] FP1/FP2/FP3 ingestion and analysis
- [x] Sector-level telemetry overlays (speed traces)
- [x] Automatic post-race report generation (PDF/DOCX export)
- [x] Undercut/overcut analysis with verdict
- [x] Journalist contextual notes via chat
- [ ] Multi-season constructor championship tracking
- [ ] Push notifications for new GP data availability
- [ ] Telemetry data persistence in DB (pending usage data analysis)
- [ ] CI/CD pipeline with automated test runs on push

---

## Acknowledgements

- [FastF1](https://github.com/theOehrly/Fast-F1) — the open-source library that makes F1 telemetry accessible
- [Anthropic](https://anthropic.com) — Claude Sonnet for natural language reasoning
- [Supabase](https://supabase.com) — PostgreSQL + Auth infrastructure