# F1 Analyst Pro

> An AI-powered Formula 1 telemetry analysis platform built for motorsport journalists. Ask questions in natural language and get structured, data-driven insights from official F1 timing data.

**Note:** All agent responses and the user interface are in Spanish, as the tool is designed for Spanish-speaking journalists and analysts.

[![Python](https://img.shields.io/badge/Python-3.11+-blue)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.x-red)](https://streamlit.io/)
[![Claude](https://img.shields.io/badge/Claude-Sonnet%204.6-orange)](https://anthropic.com/)
[![Supabase](https://img.shields.io/badge/Supabase-PostgreSQL-green)](https://supabase.com/)
[![Live](https://img.shields.io/badge/Live-f1--analyst.streamlit.app-brightgreen)](https://f1-analyst.streamlit.app/)

---

## Overview

F1 Analyst Pro combines official F1 telemetry data (via FastF1) with a Retrieval-Augmented Generation (RAG) pipeline powered by Anthropic's Claude Sonnet. The system ingests lap-by-lap telemetry, stores it in a persistent PostgreSQL database, and exposes a conversational interface where a journalist can ask complex analytical questions without writing a single query.

Typical queries include:
- "Compare Colapinto vs Gasly across all sessions this weekend"
- "What was the impact of the Safety Car on tyre strategies?"
- "Compare qualifying pace between Suzuka 2025 and 2026 — what changed with the new regulations?"

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
│   weekend_detector.py  ·  core/config.py                 │
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
└─────────────────────┘     └────────────────────────────┘
```

---

## Module Reference

### Presentation
| File | Responsibility |
|---|---|
| `app.py` | Streamlit UI — login screen, chat interface, sidebar menu, chart rendering, session state management |
| `core/chart_builder.py` | Plotly chart generation — lap times, sector comparisons, tyre degradation, pit stop strategy |

### Agent
| File | Responsibility |
|---|---|
| `core/consultant_agent.py` | RAG orchestrator — intent detection, context builder, Claude API calls, prompt caching, cost logging |
| `core/gp_resolver.py` | Parses user input into `(gp_name, year)` — handles partial names, accented characters, defaults to 2026 |
| `core/weekend_detector.py` | Detects weekend format (normal vs sprint) and returns the list of ingestable sessions |
| `core/config.py` | Central configuration — env vars, model constants, predefined analyses list |
| `core/logger.py` | Structured logging — console (INFO) + rotating file (DEBUG, 5MB × 3), token/cost metrics |

### Data
| File | Responsibility |
|---|---|
| `core/data_extractor.py` | FastF1 ingestion pipeline — extracts laps, sectors, results, stints, track status, DNF reasons |
| `core/database_manager.py` | PostgreSQL interface — all read/write operations, aggregation queries, team lineup inference |
| `supabase/migrations/` | Schema versioning — SQL migration files to run manually in the Supabase SQL Editor |

---

## Technology Stack

| Layer | Technology | Purpose |
|---|---|---|
| Language | Python 3.11+ | Entire backend and frontend |
| UI Framework | Streamlit | Web interface without JS/HTML |
| LLM | Claude Sonnet 4.6 (Anthropic) | Natural language reasoning |
| F1 Data | FastF1 | Official FOM telemetry wrapper |
| Database | PostgreSQL (Supabase) | Persistent lap and results storage |
| Auth | Supabase Auth | Per-user authentication |
| Charts | Plotly | Interactive race strategy visualizations |
| Hosting | Streamlit Cloud | Zero-infrastructure deployment |
| Version Control | GitHub | Source + schema migrations |

---

## Data Pipeline

```
FastF1 API
    │
    ▼
data_extractor.py
    │  Fetches session data (laps, results, weather)
    │  Filters: removes NaT sectors, pit-in/pit-out laps
    │  Transforms: Timedelta → float seconds, adds stint/track_status
    │
    ▼
database_manager.py
    │  INSERT ... ON CONFLICT DO NOTHING (idempotent)
    │  Tables: sessions · laps · results · qualy_results
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
    │
    ▼
Claude Sonnet 4.6
    │  Prompt caching on static context (90% token reduction on follow-up queries)
    │
    ▼
Streamlit UI
```

---

## RAG Design

The agent uses a **intent-based context routing** strategy rather than sending all available data on every query:

- `wants_qualy` → loads Q1/Q2/Q3 or SQ best laps + results
- `wants_race` → loads stint summary + classification + best laps per driver
- `wants_sprint` → loads SS/SQ data, always includes Q for cross-session comparisons
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

The system auto-detects the format via `weekend_detector.py` and adapts the sidebar menu and agent context accordingly.

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

Run the migration SQL in your Supabase SQL Editor:

```bash
cat supabase/migrations/001_initial_schema.sql
```

The RLS policies are included in `001_initial_schema.sql` and are applied in the same step.

### Run

```bash
streamlit run app.py
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

---

## User Management

Users are managed via **Supabase Authentication**:
- Add users at `supabase.com/dashboard → Authentication → Users → Add user`
- The app uses email + password login
- Sessions expire automatically; users are redirected to login on expiry
- All database access is protected by Row Level Security (RLS)

---

## Logging

Logs are written to `logs/f1_analyst.log` (excluded from git) and to the console. Each API call logs:

```
INFO [consultant_agent] API call | GP=Suzuka sessions=['Q', 'R'] input=13 output=1955 cache_write=12642 cache_read=0 cost=$0.0294 elapsed=33.98s
```

---

## Project Structure

```
f1-analyst-pro/
├── app.py                          # Streamlit entry point
├── core/
│   ├── consultant_agent.py         # RAG agent + Claude API
│   ├── chart_builder.py            # Plotly visualizations
│   ├── data_extractor.py           # FastF1 ingestion
│   ├── database_manager.py         # PostgreSQL interface
│   ├── weekend_detector.py         # Format detection
│   ├── gp_resolver.py              # Input parsing
│   ├── config.py                   # Central configuration
│   └── logger.py                   # Structured logging
├── supabase/
│   └── migrations/                 # Schema versioning
├── .env.example                    # Environment template
├── requirements.txt
└── .streamlit/
    └── config.toml                 # Dark theme
```

---

## Roadmap

- [ ] FP1/FP2/FP3 ingestion and analysis
- [ ] Sector-level telemetry overlays (speed traces)
- [ ] Automatic post-race report generation (PDF export)
- [ ] Multi-season constructor championship tracking
- [ ] Push notifications for new GP data availability

---

## Acknowledgements

- [FastF1](https://github.com/theOehrly/Fast-F1) — the open-source library that makes F1 telemetry accessible
- [Anthropic](https://anthropic.com) — Claude Sonnet for natural language reasoning
- [Supabase](https://supabase.com) — PostgreSQL + Auth infrastructure
