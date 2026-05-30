# Observe Insurance VoiceAI

Inbound claims-support assistant for Observe Insurance. The backend receives VAPI tool and call-end webhooks, verifies caller identity, retrieves claim data from Google Sheets, answers FAQ-style questions, logs completed calls, and serves a lightweight interactions dashboard.

## What It Does

- Looks up callers by phone number without exposing claim data before authentication.
- Confirms identity by caller name or date of birth.
- Composes safe claim-status responses only after server-side verification.
- Answers common support questions from the knowledge-base layer.
- Summarizes completed calls and logs interaction metadata.
- Displays call volume, containment, escalation, auth failures, sentiment, recordings, and transcripts in a static dashboard.

## Tech Stack

- Python 3.11+
- FastAPI and Uvicorn
- Google Sheets via `gspread`
- Optional Airtable FAQ source
- Optional OpenAI post-call summaries
- VAPI webhooks
- Plain HTML/CSS/JavaScript dashboard

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

`DASHBOARD_SECRET` controls access to `/api/interactions`, which returns call PII (caller phone, name, summaries, recording URLs). When set, the dashboard shows a browser prompt on first load — enter the secret once and it is held in `sessionStorage` for the session. If `DASHBOARD_SECRET` is not set the endpoint is open (acceptable for local dev, not for production). If the dashboard shows "Access denied — re-enter token", the token was wrong or cleared; refresh and enter the correct value and currently not adding it in production.

`GOOGLE_CREDENTIALS_JSON` should be the full service-account JSON pasted as a single line. Share the target spreadsheet with the service-account email before seeding or running the app.

## Google Sheets Setup

Create a spreadsheet with these tabs:

- `callers`
- `interactions`

The seed script writes the expected headers and three demo caller records.

```bash
python data/seed.py
```

Demo callers:

| Phone | Name | Claim | Status | Policy |
| --- | --- | --- | --- | --- |
| `+14085550192` | Maya Patel | `CLM-2847` | approved | `POL-100192` |
| `+13125550371` | Carlos Rivera | `CLM-3105` | requires documentation | `POL-100371` |
| `+17145550884` | Amara Okonkwo | `CLM-4422` | pending | `POL-100884` |

## Local Development

Create and activate a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Run the API:

```bash
uvicorn server.main:app --reload --host 0.0.0.0 --port 3000
```

Open:

- API health: `http://localhost:3000/health`
- Dashboard: `http://localhost:3000/client/`
- Interactions JSON: `http://localhost:3000/api/interactions`

Expose local webhooks to VAPI with a tunnel such as ngrok:

```bash
ngrok http 3000
```

## VAPI Configuration

Configure the assistant to send:

| Event | URL |
| --- | --- |
| Tool calls | `https://<your-domain>/webhook/tool` |
| End of call | `https://<your-domain>/webhook/call-end` |

Add this request header to both webhook configurations:

```text
x-vapi-secret: <VAPI_WEBHOOK_SECRET>
```

Supported tools:

| Tool | Purpose |
| --- | --- |
| `lookup_caller(phone)` | Finds a caller by phone and returns only identity fields before auth. |
| `confirm_identity(phone)` | Marks the call authenticated after the caller confirms their name. |
| `verify_identity(phone, dob)` | Verifies DOB server-side and never returns DOB to the model. |
| `answer_faq(question)` | Returns a support answer from the knowledge-base layer. |
| `compose_claim_response(phone, callId)` | Rechecks auth and claim data before producing a safe-to-speak claim response. |

## API Endpoints

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/health` | Runs service health checks. |
| `GET` | `/api/interactions` | Returns logged call interactions for the dashboard. |
| `POST` | `/webhook/tool` | Handles VAPI tool calls. |
| `POST` | `/webhook/call-end` | Logs post-call summaries and outcomes. |
| `GET` | `/client/` | Serves the static dashboard. |

## Testing

Run the test suite:

```bash
pytest
```

The tests cover phone normalization, sentiment classification, CoVe claim-response safety, and tool dispatch behavior.

## Deployment

This repo includes Render and Procfile configuration.

Render build command:

```bash
pip install -r requirements.txt
```

Render start command:

```bash
uvicorn server.main:app --host 0.0.0.0 --port $PORT
```

Set the same environment variables from `.env.example` in the hosting provider. The dashboard is served by the FastAPI app at `/client/`, so no separate frontend build step is required.
