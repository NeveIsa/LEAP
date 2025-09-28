# LEAP: Live Experiments for Active Pedagogy

An interactive learning platform that exposes Python functions as HTTP endpoints, enabling students to explore algorithms through live experimentation. Instructors create computational labs; students call functions remotely while all interactions are logged for comprehensive analytics.

## Highlights

- HTTP+JSON API with FastAPI; easy to call from any language
- Dynamic function loading from `experiments/<name>/funcs/*.py`
- Persistent logging (args, results, errors) via SQLAlchemy + DuckDB
- Simple student client (`client/client.py`) for quick onboarding
- **Unified authentication** - single login for dashboard access across all labs
- PBKDF2‑hashed credentials (240,000 iterations) with secure session management

## Project Layout

- `server/` – FastAPI app and utilities
- `client/` – Example Python client
- `experiments/<name>/` – Lab bundles:
  - `funcs/` public instructor functions
  - `ui/` HTML dashboard/pages
  - `db/` local DuckDB file (created on first run)
- `admin_credentials.json` – Global admin account (root level)

## Quick Start

Prerequisites: Python 3.10+ recommended

- Install dependencies: `pip install -r req.txt`
- Run the server: `make` or `uvicorn server.rpc_server:app --host 0.0.0.0 --port 9000`
- Open the landing page: `http://localhost:9000/`
- Log in once with global admin credentials to access all labs
- Click Launch next to a lab (e.g., `default` or `quizlab`)
- Open the lab UI from the table (e.g., `/exp/default/ui/dashboard.html`)

Tip: Use `DEFAULT_EXPERIMENT=default` to set which experiment root APIs bind to.

## Admin Credentials

Global admin credentials in `admin_credentials.json` (root level):

```
{
  "username": "admin",
  "password_hash": "<hex>",
  "salt": "<hex>",
  "iterations": 240000,
  "algorithm": "pbkdf2_sha256"
}
```

- Legacy `{ "username": "...", "password": "..." }` is auto‑migrated to the hashed format on first read.
- You can override via environment for development: `ADMIN_USERNAME`, `ADMIN_PASSWORD`.
- Default dev creds are `admin` / `password` (do not use in production).

## Running and Using

- Start: `make` or `uvicorn server.rpc_server:app --host 0.0.0.0 --port 9000`
- Health: `GET /api/health` → `{ ok, active, version }`
- List experiments: `GET /api/experiments`
- Start/stop active lab from the landing page or via `/api/experiments/*` endpoints

Root endpoints operate on the active lab and require explicit `experiment_name` when calling functions:

- `GET /functions` – list available functions and signatures
- `POST /call` – invoke a function and log the result
- `GET /logs` – query logs with filters (see below)
- `GET /log-options` – list distinct students and trials
- `GET /is-registered?student_id=<id>` – check registration
- `POST /admin/*` – admin actions (login, add students, etc.)

Sample `/call` payload:

```json
{
  "student_id": "s001",
  "func_name": "square",
  "args": [7],
  "experiment_name": "default",
  "trial": "bisection-demo"
}
```

## Logs and Filters

- Filters (query params):
  - Student: `student_id` or `sid`
  - Trial tag: `trial` or `trial_name` (legacy: `lab` or `exp`)
  - Time range: `start_time`, `end_time` (ISO 8601)
  - Limit/order: `n` (1–10,000), `order` = `latest` | `earliest`
- Examples:
  - `curl 'http://localhost:9000/logs?sid=s001&trial=bisection-demo&n=50'`
  - `curl 'http://localhost:9000/exp/default/logs?start_time=2025-09-07T00:00:00Z&end_time=2025-09-07T02:00:00Z'`

## Adding Functions (Instructors)

- Drop public functions into `experiments/<exp>/funcs/*.py` (names not starting with `_`).
- Functions are reloaded at runtime when you click “Reload” in the UI or hit the admin endpoint.

Example (`experiments/default/funcs/functions.py`):

```python
def cubic(x: float) -> float:
    """Return x^3."""
    return x * x * x
```

## Student Client

- Example client is in `client/client.py`.
- Set `STUDENT_ID` and optionally `TRIAL`. Leave `EXPERIMENT_NAME=None` to auto‑detect active, or set explicitly.
- Run with `python client/client.py`.

## QuizLab Quizzes

- Authoring
  - Place quiz Markdown files under `experiments/<lab>/ui/quiz/` (e.g., `questions.md`, `derivatives.md`).
  - Question header: `## Question <num>: <id>` (e.g., `## Question 1: q1`).
  - Prompt: first bold line is the question (e.g., `**Derivative of x^2**`).
  - Choices and type:
    - Single‑choice (radio): lines start with `A)`, `B)`, ...
    - Multi‑choice (checkbox): lines start with `A]`, `B]`, ...
    - Correct choices end with a trailing `✓`.
  - Markdown in prompts/choices:
    - Fenced code blocks (```lang) and inline code
    - LaTeX math via `$...$` and `$$...$$`

- Quiz page: `/exp/quizlab/ui/quiz.html`
  - Auto‑detects quiz files via `GET /exp/<lab>/files?ext=md&dir=quiz` (with a local fallback probe).
  - Dropdown to choose the quiz; per‑question submit logs an answer via `/call`.
  - Registration pill checks `GET /is-registered?student_id=...`.
  - Submissions include `quizname` (file name without `.md`).
  - Payloads:
    - Single: `{ kind:'quiz', type:'single', quizname, qid, question, choice_index, choice_text, ts }`
    - Multi: `{ kind:'quiz', type:'multi', quizname, qid, question, choice_indices:[...], choice_texts:[...], ts }`

- Stats page: `/exp/quizlab/ui/quiz-stats.html?quiz=<name>[&trial=<trial>]`
  - Charts‑only per‑question distributions; optional dedupe by latest per student.
  - CSV export; truncation banner when exactly 10,000 logs are returned.

- API additions
  - `GET /exp/<lab>/files?ext=md&dir=quiz` → `{ files: ["questions.md", ...] }`

- Authoring guide: see `experiments/quizlab/ui/QUIZ_AUTHORING.md`

## Notes & Tips

- Databases: Local DuckDB files live under `experiments/<exp>/db/` and are ignored by Git.
- Sessions: A secure random session secret is generated if `SESSION_SECRET_KEY` is not set. Set it for production.
- CORS: Adjust `server/rpc_server.py` if you plan to call from browsers hosted elsewhere.
- Dev flow: Most changes are hot‑reloaded by restarting Uvicorn; function additions require reload via admin.

## Tech Stack

- FastAPI, Uvicorn
- SQLAlchemy 2.0, DuckDB (duckdb-engine)
- Marimo (optional dashboard labs)
- Python client via `requests`
 
## Shared UI Templates (Students + Logs)

To avoid duplicating student and log pages across experiments, this repo includes minimal, reusable templates.

- Location: `templates/`
  - `templates/students.html` – add/list/delete students; clear logs for a student
  - `templates/logs.html` – view logs with filters (student, trial, order, time window)
- Styling and theming:
  - Each lab can provide an optional theme at `experiments/<exp>/ui/style/theme.css`.
  - The templates include `<link rel="stylesheet" href="style/theme.css">` so the lab’s theme is automatically applied when the file is served under the lab’s UI.
- Recommended usage (symlink into each lab):

```
# Students page
ln -s ../../../templates/students.html experiments/<exp>/ui/students.html
# Logs page
ln -s ../../../templates/logs.html experiments/<exp>/ui/logs.html
# Optional theme override (create/edit)
mkdir -p experiments/<exp>/ui/style
printf "/* custom overrides */\n" > experiments/<exp>/ui/style/theme.css
```

Open the pages at `/exp/<exp>/ui/students.html` and `/exp/<exp>/ui/logs.html`.
