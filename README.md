# BankAI Platform

BankAI is a local banking application with a FastAPI backend and two command
line interfaces: a menu-driven banking CLI and a natural-language assistant
powered by the OpenAI Agents SDK with Google's Gemini OpenAI-compatible API.

## Contents

- [Features](#features)
- [Architecture](#architecture)
- [Requirements](#requirements)
- [Installation](#installation)
- [Configuration](#configuration)
- [Run the application](#run-the-application)
- [Banking and support capabilities](#banking-and-support-capabilities)
- [API documentation](#api-documentation)
- [Tests](#tests)
- [Security and data notes](#security-and-data-notes)
- [Project structure](#project-structure)

## Features

- User registration, login, and bearer-token authentication.
- Account, balance, transaction, beneficiary, payment, and support-ticket APIs.
- Menu-driven CLI for directly using backend routes.
- Natural-language triage between the Banking Agent and IT Support Agent.
- Human approval for payments, with verified beneficiary/payment details shown
  before submission.
- Interactive collection of missing account, beneficiary, and ticket details.
- Per-user account and ticket access enforced by the backend.
- Input/output guardrails on the agent hierarchy.

## Architecture

```text
User
  |
  +-- Menu CLI ----------------------------+
  |                                        |
  +-- Agent CLI -> Triage Agent             |
                    +-- Banking Agent ------+--> FastAPI backend --> SQLite
                    +-- IT Support Agent ---+
```

The agent layer authenticates through the backend and keeps the access token in
the running process. It does not connect directly to the SQLite database. The
backend is the authority for authentication, ownership checks, and persisted
banking data.

## Requirements

- Windows PowerShell (commands below use PowerShell syntax).
- Python 3.11 or newer.
- The packages listed in the single root [`requirements.txt`](./requirements.txt).
- A Gemini API key to use the natural-language agent CLI.

The root requirements file includes the backend, agent CLI, and HTTP client
dependencies. SQLite is provided by Python and needs no separate package.

## Installation

Run these commands from the repository root:

```powershell
Set-Location D:\Python\Project\bank-ai-platform
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If PowerShell does not allow activation, invoke the interpreter directly as
shown in the following commands:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Configuration

Create local `.env` files as needed. Both are ignored by Git; do not commit API
keys, passwords, or signing secrets.

### Backend: `backend\.env`

The backend requires a JWT signing key:

```dotenv
JWT_SECRET_KEY=replace-with-a-long-random-secret
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

Generate a suitable local key with:

```powershell
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(48))"
```

Copy the generated value to `JWT_SECRET_KEY`. Keep the same key while existing
tokens need to remain valid. The backend loads `.env` relative to its working
directory, so start it from `backend`.

### Agent CLI: `agent_layer\.env`

```dotenv
GEMINI_API_KEY=your-gemini-api-key
GEMINI_MODEL=gemini-3.8-flash
BANKING_BACKEND_URL=http://127.0.0.1:8000
BANKING_BACKEND_TIMEOUT_SECONDS=10
AGENT_TRACING_ENABLED=false
```

Agent tracing is disabled by default. To enable OpenAI Agents SDK trace export,
set `AGENT_TRACING_ENABLED=true` and provide `OPENAI_API_KEY`; this key is used
for tracing, not for Gemini model requests. The Gemini key remains
`GEMINI_API_KEY`.

`BANKING_BACKEND_URL` and `BANKING_BACKEND_TIMEOUT_SECONDS` are optional and
default to `http://127.0.0.1:8000` and `10` seconds.

## Run the application

Start the backend in its own PowerShell terminal:

```powershell
Set-Location D:\Python\Project\bank-ai-platform\backend
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

The API listens at `http://127.0.0.1:8000`. Keep it running while using either
CLI.

### Create the first user

Before the first CLI login, create a user through the backend Swagger UI:

1. Open `http://127.0.0.1:8000/docs`.
2. Expand `POST /create_user` and choose **Try it out**.
3. Submit a JSON body such as:

   ```json
   {
     "name": "Example User",
     "email": "user@example.com",
     "password": "choose-a-strong-password"
   }
   ```

4. Use that email and password when the CLI prompts for login.

The password is sent only to the local backend during registration/login; use
a unique password for development and never paste production credentials into
the example.

### Menu-driven banking CLI

In a second terminal:

```powershell
Set-Location D:\Python\Project\bank-ai-platform\agent_layer
..\.venv\Scripts\python.exe -m agent_app.cli.chat
```

The CLI checks the backend, prompts for login (password input is hidden), then
shows a numbered menu. Enter `help` to redisplay the menu or `exit` to quit.
Pass `--check-backend` to authenticate and exit without opening the menu. The
backend URL can be set with `BANKING_BACKEND_URL` or `--backend-url`.

### Natural-language banking and support agent

Create `agent_layer\.env` with a Gemini API key, then launch from `agent_layer`:

```powershell
Set-Location D:\Python\Project\bank-ai-platform\agent_layer
..\.venv\Scripts\python.exe main.py
```

The same CLI can be started as a module:

```powershell
..\.venv\Scripts\python.exe -m agent_app.cli.banking_chat
```

Use `--help` to see command-line options. The CLI prompts for backend login,
then accepts requests in natural language. Type `exit` or `quit` to close it.

## Banking and support capabilities

### Banking Agent

- Check the authenticated user's account, balance, transactions, and saved
  beneficiaries.
- Create an account if the user does not already have one. The user supplies an
  account type; the backend generates the account number. A second account is
  rejected.
- Create beneficiaries, prompting for missing name, account number, or bank
  name.
- Submit payments to saved beneficiaries only after explicit approval. The CLI
  displays and verifies the recipient and amount before asking for `yes` or
  `no`.

### IT Support Agent

- Handle suspected fraud, suspicious activity, complaints, and general banking
  issues.
- Create support tickets after collecting any missing title, description,
  category, and priority.
- Retrieve a ticket belonging to the authenticated user by ticket ID.

### Guardrails

Input checks reject oversized messages, credential-sharing patterns, attempts
to override or reveal agent instructions, and requests for another user's
private banking information. Output checks reject non-text/empty or oversized
responses and patterns that appear to expose authentication secrets. These
checks are safety filters, not a replacement for backend authorization or
human review.

## API documentation

With the backend running, use:

- Health check: `http://127.0.0.1:8000/health`
- Swagger UI: `http://127.0.0.1:8000/docs`
- OpenAPI schema: `http://127.0.0.1:8000/openapi.json`

The API uses bearer tokens returned by `/login`. Authenticated requests are
made through the CLIs; do not put tokens in command-line arguments.

## Tests

Run the agent-layer tests from the repository root:

```powershell
Set-Location D:\Python\Project\bank-ai-platform\agent_layer
..\.venv\Scripts\python.exe -m unittest discover -s tests
```

Run backend tests, when present:

```powershell
Set-Location D:\Python\Project\bank-ai-platform\backend
..\.venv\Scripts\python.exe -m unittest discover -s tests
```

## Security and data notes

- Keep `backend\.env` and `agent_layer\.env` private and out of version control.
- Use a unique, randomly generated `JWT_SECRET_KEY`; never use a sample value
  in production.
- The backend currently uses a local SQLite database at
  `backend\app\database\database.db` when started from the documented
  directory. Back up this file before deleting or replacing it.
- This project is a development banking application. Do not use it to store or
  transfer real funds or real customer data without a security, privacy, and
  compliance review.

## Project structure

```text
bank-ai-platform/
├── agent_layer/
│   ├── agent_app/
│   │   ├── agents/          # Banking, support, and triage agents
│   │   ├── backend_client/  # Authenticated HTTP client and API adapters
│   │   ├── cli/             # Menu and natural-language command-line apps
│   │   ├── tools/           # Banking and support agent tools
│   │   ├── guardrails.py    # Shared agent input/output checks
│   │   └── main.py          # Agent CLI entry point
│   ├── tests/               # Agent and client tests
│   └── main.py              # Direct agent-layer entry point
├── backend/
│   ├── app/
│   │   ├── api/             # FastAPI route handlers
│   │   ├── database/        # SQLAlchemy setup and model exports
│   │   ├── models/          # Database models
│   │   ├── schemas/         # Pydantic request/response schemas
│   │   └── main.py          # FastAPI application
│   └── tests/               # Backend tests
├── requirements.txt         # All project Python dependencies
└── README.md
```
