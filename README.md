# Automatom — BriefRunner

**A Professional Agent that turns repetitive requests into reviewable background briefs.**

Automatom is a small, inspectable workflow runtime for professionals who repeat
the same research and status-reporting work every week. Its hackathon agent,
**BriefRunner**, accepts a plain-language request such as “prepare my weekly
competitor brief,” gathers bounded context, drafts a structured brief, and
stops at an explicit human approval boundary before any notification could be
sent.

## Why this matters

Busy teams do not need another chat answer; they need dependable progress on
the repetitive work behind a decision. BriefRunner makes that work visible and
reviewable. The person remains the decision-maker, while the agent handles the
first pass and records what happened.

## How it works

1. A user submits an intent through the FastAPI API.
2. The background runner creates an inspectable workflow run.
3. The Strands Agents SDK path uses two bounded, read-only tools: lookup of
   demo context and brief drafting. With AWS credentials and a Bedrock model,
   this path runs through `BedrockModel`.
4. The default offline mode produces deterministic context so judges can run
   the demo without cloud credentials.
5. The result is `awaiting_approval`; `POST /runs/{runUid}/approve` changes the
   state to `approved` but still leaves `sent: false`. No message is sent
   automatically.

This architecture follows the Strands Agents SDK pattern of composing an
`Agent` with decorated tools, while keeping the demo honest and reproducible.

## Quick start

```bash
cd app
python -m pip install -e .
uvicorn main:app --reload --port 8000
```

The Strands and AWS dependencies are included for the cloud-backed path. For
the deterministic local demo, no AWS credentials are needed. To opt into the
Strands path, set `AUTOMATOM_AGENT_MODE=strands`, `STRANDS_MODEL_ID` (for
example `amazon.nova-lite-v1:0`), and `AWS_REGION`.

## Demo

```bash
curl -X POST http://localhost:8000/demo-runs \
  -H "content-type: application/json" \
  -d '{"intent":"Prepare a weekly competitor brief"}'
```

Poll the returned `runUid`:

```bash
curl http://localhost:8000/runs/<runUid>
```

The completed `result` contains `agentMode`, `brief`,
`notificationStatus: "pending_approval"`, `approvalRequired: true`, and
`sent: false`. After reviewing the brief, approve it explicitly:

```bash
curl -X POST http://localhost:8000/runs/<runUid>/approve
```

Approval is intentionally a state transition, not an automatic outbound
action. A real integration would add a separately authenticated sender after
the approval boundary.

## API

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/workflows` | Create a workflow from intent and steps |
| `POST` | `/runs` | Start a workflow and return immediately |
| `POST` | `/demo-runs` | Start the BriefRunner demo agent |
| `GET` | `/runs/{run_uid}` | Fetch run status and output |
| `POST` | `/runs/{run_uid}/approve` | Approve a prepared result without sending |
| `GET` | `/health` | Check runtime availability |

## Safety and scope

BriefRunner has no arbitrary shell tool, no uncontrolled outbound messaging,
and no claim of live competitor data in offline mode. Its tool surface is
bounded, the output is persisted in SQLite, and every demo notification stops
for human review. Production integrations should add scoped credentials,
sandboxed execution, audit logging, and an authenticated approval workflow.

## Verification

```bash
python -m unittest -v tests.test_strands_runtime tests.test_demo_contract
```

The tests cover the offline brief contract, the approval transition, and the
API-facing camel-case result payload.

## Hackathon submission

- Track: **Professional Agents**
- SDK: **Strands Agents SDK** with an optional Amazon Bedrock model
- Architecture diagram: `output/automatom-brief-runner-architecture.pdf`
- Demo video: `output/automatom-brief-runner-demo.webm`

## License

MIT


## Google-native hackathon mode

The `hackathon/all-things-agentic-google-native` branch adds a bounded Gemini path for the All Things Agentic Hackathon while preserving the deterministic offline demo and the existing optional Strands/Bedrock path. The Google path uses the Google GenAI SDK through `google_runtime.py`: it prepares a reviewable brief, records uncertainty, and never sends notifications or performs irreversible actions.

### Local Gemini API-key mode

```bash
cd app
python -m pip install -e .
export AUTOMATOM_AGENT_MODE=gemini
export GEMINI_API_KEY=your_key_here
export GEMINI_MODEL=gemini-3.5-flash
uvicorn main:app --reload --port 8000
```

### Vertex AI / Gemini Enterprise Agent Platform mode

The adapter also supports Google Cloud Application Default Credentials, which avoids putting a service-account key or Gemini API key in the repository. After authenticating ADC locally with an approved Google Cloud account, use:

```bash
cd app
python -m pip install -e .
export AUTOMATOM_AGENT_MODE=gemini
export GOOGLE_GENAI_USE_ENTERPRISE=true
export GOOGLE_CLOUD_PROJECT=your-project-id
export GOOGLE_CLOUD_LOCATION=us
export GEMINI_MODEL=gemini-3.5-flash
uvicorn main:app --reload --port 8000
```

The public Cloud Run service has been verified with this Vertex ADC configuration. Its current service URL is `https://automatom-briefrunner-447035175931.us-central1.run.app`, and the verified revision uses `GOOGLE_CLOUD_LOCATION=us`. The Cloud Run runtime service account requires the least-privilege `roles/aiplatform.user` role. Do not commit credentials or paste them into the README.

To run safely without cloud credentials, keep `AUTOMATOM_AGENT_MODE=offline`. Offline mode is a deterministic development and judge-fallback path; it must not be described as live Gemini behavior. In every mode, the approval boundary remains enabled: approval changes the result state, but `sent` remains `false`.

The hackathon submission must additionally include a public hosted URL, a repository URL, this spin-up guide, a Google/Gemini architecture diagram, and a public demo video no longer than four minutes showing the asynchronous run, the Gemini-generated brief when Gemini mode is enabled, the approval checkpoint, and Cloud Run evidence. The repository intentionally does not include secrets.
