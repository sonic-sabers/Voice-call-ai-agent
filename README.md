# Observe Insurance VoiceAI

Take-home assignment for Observe Insurance. Inbound claims-support voice agent — authentication, claim status, FAQ, escalation, and post-call logging — built with VAPI, Python/FastAPI, Google Sheets, and Airtable.

**Live demo:** https://www.heyashish.dev/voice-ai

## Assignment Coverage

| Requirement | Implementation |
| --- | --- |
| Greeting & authentication | VAPI agent greets, collects phone, looks up caller in Google Sheets, confirms identity by name or DOB |
| Claim status | `compose_claim_response` re-fetches and CoVe-validates data before speaking — claim data never returned to LLM until auth passes |
| Documentation instructions | Injected into claim response when status is `requires documentation` |
| FAQ support | `answer_faq` tool — office hours, mailing address, new claim process, general claims info |
| Escalation & safety | Escalation path to live representative; graceful handling of unsupported questions and emergency language |
| Post-call logging | `call-end` webhook writes caller name, summary, sentiment, and timestamp back to Google Sheets |
| Happy path | Auth → claim status → FAQ → close |
| Auth failure flow | Three-strike lockout, call ends gracefully |
| Customer not found | Distinct message, offered to re-enter or escalate |
| Escalation flow | Transfers to representative queue |
| Multi-agent (bonus) | VAPI squad — triage agent (auth) → claims agent (status + FAQ) |
| Knowledge base (bonus) | Airtable FAQ table via `pyairtable` |

## What It Does

- Looks up callers by phone number without exposing claim data before authentication.
- Confirms identity by caller name or date of birth (DOB compared server-side — never returned to the LLM).
- Composes safe claim-status responses only after server-side CoVe re-verification.
- Answers common support questions from the Airtable knowledge-base layer.
- Summarizes completed calls (Claude Haiku) and logs interaction metadata back to Google Sheets.
- Displays call volume, containment rate, escalation rate, auth failures, sentiment, recordings, and transcripts in a static dashboard.

## Tech Stack

- Python 3.11+, FastAPI, Uvicorn
- VAPI — voice pipeline (Deepgram STT, ElevenLabs TTS, Claude Sonnet 4.6)
- Google Sheets via `gspread` — integration #1 (caller lookup) + integration #2 (post-call log)
- Airtable via `pyairtable` — integration #3 / FAQ knowledge base
- Claude Haiku via Anthropic SDK — post-call summary generation
- Plain HTML/CSS/JavaScript dashboard (no build step)

## Project Structure

```text
.
├── client/
│   ├── index.html          # Dashboard UI
│   ├── app.js              # Polls /api/interactions
│   ├── constants.js        # Client constants
│   └── styles.css
├── data/
│   └── seed.py             # Seeds demo callers and sheet headers
├── server/
│   ├── main.py             # FastAPI app, middleware, routers, static client mount
│   ├── core/               # Config, auth, phone normalization, logging, state
│   ├── routes/             # Health, interactions, VAPI webhook routes
│   ├── services/           # Sheets, FAQ, CoVe, summaries, tool dispatch
│   └── models/             # Typed domain models
├── tests/                  # Unit tests
├── .env.example            # Environment template
├── Procfile                # Heroku-style process command
├── render.yaml             # Render deployment config
└── requirements.txt
```

## Demo Callers

Three seeded accounts for demo flows:

| Phone | Name | Claim | Status | Policy |
| --- | --- | --- | --- | --- |
| `+14085550192` | Maya Patel | `CLM-2847` | approved | `POL-100192` |
| `+13125550371` | Carlos Rivera | `CLM-3105` | requires documentation | `POL-100371` |
| `+17145550884` | Amara Okonkwo | `CLM-4422` | pending | `POL-100884` |

**Suggested demo flows:**

1. **Happy path** — call as Maya Patel, authenticate, get claim status, ask an FAQ, close
2. **Documentation flow** — call as Carlos Rivera, get claim status → agent provides doc submission instructions
3. **Auth failure** — provide wrong name three times → lockout and graceful end
4. **Customer not found** — provide a phone not in the sheet → not-found branch
5. **Escalation** — say "I want to speak to a representative" at any point

## Architecture Notes

**CoVe on claim responses:** `compose_claim_response` re-fetches the caller record from Google Sheets and runs a verification step before the LLM speaks any claim data. Claim fields are never returned to the model raw — they're composed into a pre-checked string.

**DOB privacy:** `verify_identity` compares DOB server-side. The value never reaches the LLM context.

**In-memory auth state:** `authenticated_calls` dict keyed by VAPI call ID. Sufficient for demo concurrency; swap for Redis in production.

**Multi-agent squad:** VAPI squad routes triage agent (authentication) → claims agent (status + FAQ) on successful auth. Each agent has a focused system prompt.

**Post-call summary:** Claude Haiku generates a natural-language summary from the transcript after the call ends. Haiku chosen for cost/latency on a non-realtime path.

## Environment

Copy the example file and fill in real values:

```bash
cp .env.example .env
```

Required:

```env
VAPI_WEBHOOK_SECRET=your-webhook-secret-here
GOOGLE_SPREADSHEET_ID=your-spreadsheet-id-here
GOOGLE_CREDENTIALS_JSON={"type":"service_account","project_id":"..."}
```

Optional:

```env
AIRTABLE_API_KEY=your-airtable-api-key-here
AIRTABLE_BASE_ID=your-airtable-base-id-here
OPENAI_API_KEY=your-openai-api-key-here
DASHBOARD_SECRET=your-dashboard-secret-here
PORT=3000
```

`DASHBOARD_SECRET` controls access to `/api/interactions`, which returns call PII (caller phone, name, summaries, recording URLs). When set, the dashboard shows a browser prompt on first load — enter the secret once and it is held in `sessionStorage` for the session. If `DASHBOARD_SECRET` is not set the endpoint is open (acceptable for local dev, not for production).

`GOOGLE_CREDENTIALS_JSON` should be the full service-account JSON pasted as a single line. Share the target spreadsheet with the service-account email before seeding or running the app.

## Google Sheets Setup

Create a spreadsheet with two tabs: `callers` and `interactions`.

Seed headers and demo records:

```bash
python data/seed.py
```

## Local Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn server.main:app --reload --host 0.0.0.0 --port 3000
```

Open:

- API health: `http://localhost:3000/health`
- Dashboard: `http://localhost:3000/client/`
- Interactions JSON: `http://localhost:3000/api/interactions`

Expose local webhooks to VAPI:

```bash
ngrok http 3000
```

## VAPI Configuration

Configure the assistant to send:

| Event | URL |
| --- | --- |
| Tool calls | `https://<your-domain>/webhook/tool` |
| End of call | `https://<your-domain>/webhook/call-end` |

Add request header to both webhook configs:

```text
x-vapi-secret: <VAPI_WEBHOOK_SECRET>
```

Supported tools:

| Tool | Purpose |
| --- | --- |
| `lookup_caller(phone)` | Finds caller by phone, returns only identity fields before auth |
| `confirm_identity(phone)` | Marks call authenticated after caller confirms name |
| `verify_identity(phone, dob)` | Compares DOB server-side, never returns DOB to model |
| `answer_faq(question)` | Returns support answer from Airtable knowledge base |
| `compose_claim_response(phone, callId)` | Re-checks auth and claim data, returns safe-to-speak response |

## API Endpoints

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/health` | Service health checks |
| `GET` | `/api/interactions` | Logged call interactions for dashboard |
| `POST` | `/webhook/tool` | VAPI tool call handler |
| `POST` | `/webhook/call-end` | Post-call summary and logging |
| `GET` | `/client/` | Static dashboard |

## Testing

```bash
pytest
```

Covers phone normalization, sentiment classification, CoVe claim-response safety, and tool dispatch behavior.

## Deployment

Includes Render and Procfile configuration.

Build command:

```bash
pip install -r requirements.txt
```

Start command:

```bash
uvicorn server.main:app --host 0.0.0.0 --port $PORT
```

Set environment variables from `.env.example` in the hosting provider. Dashboard served by FastAPI at `/client/` — no separate frontend build step.
