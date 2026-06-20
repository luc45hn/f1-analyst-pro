# Contributing to F1 Analyst Pro

Thanks for your interest in contributing! This is a personal project but PRs and issues are welcome.

## Reporting bugs

Open an issue with:
- What you asked the app
- What GP and session was loaded
- The error message or unexpected behavior

## Suggesting features

Open an issue describing the use case. Bonus points if you include a real F1 example of why it would be useful.

## Contributing code

1. Fork the repo
2. Create a branch: `git checkout -b feat/your-feature`
3. Make your changes
4. Run the test suite: `pytest tests/`
5. Open a PR against `main`

## Project structure

| Module | Purpose |
|---|---|
| `app.py` | Streamlit frontend and auth |
| `core/consultant_agent.py` | RAG orchestrator and intent detection |
| `core/data_extractor.py` | FastF1 ingestion pipeline |
| `core/database_manager.py` | SQL queries and analysis functions |
| `core/chart_builder.py` | Plotly chart generation |
| `core/export_manager.py` | DOCX and PDF export |
| `core/weekend_detector.py` | GP lookup and session management |
| `supabase/migrations/` | Database schema |

## Stack

FastF1 · Claude Sonnet · Supabase · Streamlit · Plotly · python-docx · reportlab
