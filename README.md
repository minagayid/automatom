# Automatom

**Universal AI workflow & agent automation platform.**

Automatom lets you turn a plain-text intent into a structured, runnable workflow in one API call. It exposes a minimal REST surface — `POST /workflows`, `POST /runs`, `GET /runs/:id` — backed by a SQLite store and a pluggable step engine.

## Features

- **Intent → Workflow** — Describe what you want in plain language; Automatom scaffolds the steps
- - **Workflow Engine** — LLM, HTTP, code, and approval steps out of the box
  - - **Run Tracking** — Every run is persisted with status, timestamps, and step output
    - - **FastAPI + Pydantic** — Auto-generated Swagger at `/docs`
      - - **SQLite-backed** — Zero external dependencies for local development
       
        - ## Quick Start
       
        - ```bash
          cd app
          pip install -r pyproject.toml   # or: pip install fastapi uvicorn pydantic aiosqlite
          uvicorn main:app --reload --port 8000
          ```

          Visit http://localhost:8000/docs for interactive API docs.

          ## API

          | Method | Path | Description |
          |--------|------|-------------|
          | `POST` | `/workflows` | Create a workflow from intent + steps |
          | `POST` | `/runs` | Start a run for a workflow |
          | `GET` | `/runs/{run_uid}` | Fetch run status and output |

          ## Project Structure

          ```
          automatom/
          ├── app/
          │   ├── agents/          # Agent definitions and tools
          │   ├── engine/          # Step execution engine
          │   ├── services/        # Persistence (records, runs)
          │   ├── main.py          # FastAPI entrypoint
          │   ├── schemas.py       # Pydantic models
          │   ├── engine.py        # Workflow execution loop
          │   └── pyproject.toml   # Dependencies
          └── README.md
          ```

          ## License

          MIT
