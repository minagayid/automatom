# Pre-existing Work Disclosure

This document is part of the All Things Agentic Hackathon submission for **Automatom — BriefRunner**. It identifies the work that predates the Submission Period and the hackathon-specific work completed during the Submission Period. The goal is transparency, not a claim that the entire repository was newly written.

## Disclosure summary

| Component | Provenance | How it is used in this submission |
|---|---|---|
| Generic Automatom workflow prototype | Pre-existing, authored by the entrant before the Submission Period | Provides generic Pydantic workflow schemas, a basic FastAPI request/run structure, and local SQLite persistence patterns. It is not represented as hackathon-created work. |
| Python, FastAPI, Pydantic, Uvicorn, SQLite/aiosqlite | Standard open-source development tools and libraries, used under their respective licenses | Used to package, validate, serve, and persist the demo workflow. |
| BriefRunner product behavior | Created and substantially revised during the Submission Period | Adds the bounded professional-brief workflow, asynchronous run demonstration, explicit human approval checkpoint, documentation, and tests. |
| Google-native integration | Created and substantially revised during the Submission Period | Adds the Google Gen AI SDK adapter, Gemini-on-Vertex-AI configuration, Cloud Run containerization, non-secret runtime metadata, and Google-native architecture documentation. |
| Demo materials | Created for this submission during the Submission Period | The final public video will show the actual Google Cloud deployment and live agent run. No third-party proprietary data is used in the demonstration. |

## Pre-existing code incorporated

The entrant previously created the generic **Automatom** prototype. The following portions are incorporated as a starting point and are disclosed as pre-existing: generic workflow schemas in `app/schemas.py`; broad workflow and scheduling experimentation in `app/engine.py`; the local run-state persistence pattern in `app/services/records.py`; and the generic workflow create/run routes in `app/main.py`.

This baseline is owned by the entrant and licensed MIT in the original project. It is included because it supplies a small inspectable workflow shell, not because it fulfils the hackathon challenge by itself. It did not contain the Google-native BriefRunner implementation described below.

## Hackathon-specific work

The work represented as the hackathon project is the **BriefRunner** agent and its Google Cloud delivery path. During the Submission Period, the entrant created and iterated on the following capabilities:

1. A professional-background-workflow experience that converts a plain-language recurring briefing request into an inspectable asynchronous run.
2. The `awaiting_approval` / `approved_for_send` state machine, with `sent: false` enforced before and after approval.
3. The Gemini adapter in `app/google_runtime.py`, using the Google Gen AI SDK and Vertex AI Application Default Credentials.
4. Cloud Run packaging in `Dockerfile`, a reproducible dependency manifest, spin-up instructions, an architecture diagram, and testing instructions.
5. A submission narrative and video plan that show real Cloud Run and Gemini evidence rather than presenting the deterministic fallback as a live model call.

## Third-party tools, data, and credentials

The project uses the Google Gen AI SDK to access Gemini through Vertex AI, plus the standard Python libraries named in `requirements-google.txt`. The demonstration uses only a user-provided sample request and deterministic context when running offline; it does not ingest proprietary datasets, scrape third-party data, or include a third-party API key in the repository. Cloud Run uses Application Default Credentials or a configured service account; no credential material is checked in.

## Scope statement for Devpost

The Devpost submission should link to this repository, include the text below or an equivalent disclosure, and avoid suggesting that the older generic Automatom prototype was created for this hackathon:

> BriefRunner’s hackathon-specific agent workflow, Gemini-on-Vertex-AI adapter, Cloud Run deployment, architecture, test updates, and submission materials were built during the Submission Period. I incorporated my own pre-existing generic Automatom workflow scaffolding (basic FastAPI schemas, local run-state persistence, and non-agent workflow routes) as a disclosed starting point. The reused code is owned by me and MIT licensed; the Google-native BriefRunner functionality submitted here is the new work.
