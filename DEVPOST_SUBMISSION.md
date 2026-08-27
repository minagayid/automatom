# Devpost Submission Copy — Automatom — BriefRunner

Use this copy in the **All Things Agentic Hackathon** submission editor. Replace the two bracketed URLs only after verifying the public Cloud Run service and publishing the final public video. Do not submit the old AWS/Strands description or an offline-mode video as Gemini evidence.

## Project name

**Automatom — BriefRunner**

## Tagline

**An approval-gated Gemini agent that turns recurring professional requests into reviewable background briefs.**

## Category

**Taskmaster**

## Project links

| Devpost field | Value |
|---|---|
| Code repository | `https://github.com/minagayid/automatom-briefrunner` |
| Hosted project | `[verified Cloud Run .run.app URL]/docs` |
| Demo video | `[public YouTube or Vimeo URL, maximum 4 minutes]` |

## Inspiration

Professionals repeatedly lose time to the work between a request and a decision: preparing weekly status updates, synthesizing changes, and producing a first recommendation. A chat response is insufficient because the user needs work to continue in the background and remain reviewable before anything consequential happens.

## What it does

BriefRunner accepts a plain-language briefing request and starts an asynchronous, inspectable workflow. In its Google-native production path, the agent uses Gemini 3.5 Flash through Vertex AI to draft a concise brief with the audience, findings, uncertainty, recommended next action, and an explicit approval checkpoint. The API exposes the run state so the user can review the work. Approval records an approved handoff only; it never sends a notification automatically.

## How we built it

The backend is a FastAPI service deployed on **Google Cloud Run**. The background BriefRunner workflow invokes **Gemini 3.5 Flash through Vertex AI** using the **Google Gen AI SDK**, which is the Google agent framework used by this project. The run is persisted in a small SQLite store for this demonstration and exposed through status endpoints. The agent has a deliberately bounded scope: it does not claim live data without being given it, execute arbitrary tools, or make irreversible changes.

The repository includes a Dockerfile, exact dependency manifest, architecture diagram, local spin-up guide, Cloud Run deployment instructions, tests, and a non-secret `/health` endpoint that reports the selected agent mode and Google runtime metadata. The demo video shows the live Cloud Run service, Gemini-mode agent run, returned brief, approval transition, and the fact that `sent` remains `false`.

## Challenges we ran into

The key engineering challenge was preserving a credible asynchronous workflow while keeping the agent’s action boundary honest. The implementation separates the request, background work, persisted status, reviewable output, and approval transition. We also changed the runtime to use the supported Google Gen AI SDK Vertex AI client configuration and removed the legacy AWS/Strands path from the submission repository so the required technologies are directly verifiable.

## Accomplishments that we are proud of

We built a real, inspectable agent workflow rather than a generic chat screen. BriefRunner makes its state visible, labels uncertainty, returns control to a person before external action, and provides a reproducible path for a reviewer to verify the Gemini, Google Gen AI SDK, and Cloud Run integration.

## What we learned

An agentic workflow is most useful when it makes progress without hiding what happened. The product contract matters: by making approval and `sent: false` observable in the API result, the system can demonstrate autonomy for research and drafting while maintaining a human decision boundary.

## What’s next

The next step is to replace the demonstration’s local run-state store with a managed persistence service and add narrowly scoped, authenticated connectors that can act only after the user approves the proposed handoff. Those production improvements would retain the same inspectable state transitions and human-control boundary.

## Built with

- Google Gen AI SDK (`google-genai`)
- Gemini 3.5 Flash
- Vertex AI
- Google Cloud Run
- Cloud Logging
- FastAPI
- Python
- SQLite / aiosqlite

## Required disclosure

BriefRunner’s hackathon-specific agent workflow, Gemini-on-Vertex-AI adapter, Cloud Run deployment, architecture, test updates, and submission materials were built during the Submission Period. I incorporated my own pre-existing generic Automatom workflow scaffolding—basic FastAPI schemas, local run-state persistence, and non-agent workflow routes—as a disclosed starting point. The reused code is owned by me and MIT licensed; the Google-native BriefRunner functionality submitted here is the new work. The repository contains a detailed `PRE_EXISTING_WORK.md` disclosure.
