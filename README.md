# Interactive Classroom for Numerical Methods

This project provides a client-server framework for teaching numerical optimization and root-finding techniques. Students use a client to remotely call and test mathematical functions. The server executes the functions, logs every attempt to a database, and provides a foundation for a real-time dashboard to visualize student progress.

## Features

- **JSON-RPC Style API Server**: A robust server built with FastAPI that exposes numerical functions.
- **Dynamic Function Loading**: Instructors can add new Python functions on the fly, and the server automatically makes them available to students.
- **Persistent Logging**: Logs all student submissions (arguments, results, and errors) to a local DuckDB database.
- **Simple Student Client**: An intuitive Python client that abstracts away API calls, allowing students to call remote functions as if they were local.
- **SQLAlchemy ORM**: Clean and robust database interaction layer.
- **Dashboard Ready**: Includes a Marimo notebook to easily build a real-time monitoring dashboard.
- **Security**: Supports PBKDF2-hashed admin passwords; legacy plaintext files still work.

Hashed admin_credentials.json (example)
--------------------------------------
Use this format in `experiments/<experiment>/admin_credentials.json`:

```
{
  "username": "admin",
  "password_hash": "5f0d...",   
  "salt": "9ab3...",
  "iterations": 240000,
  "algorithm": "pbkdf2_sha256"
}
```

Tip: You can temporarily set `ADMIN_USERNAME`/`ADMIN_PASSWORD` in the environment; the server will hash them in-memory on startup and accept those credentials.

## Tech Stack

- Python
- FastAPI (for the server)
- Uvicorn (to run the server)
- SQLAlchemy 2.0 (for the database ORM)
- DuckDB (for the database engine)
- Marimo (for the dashboard)

## Setup and Usage

### 1. Installation

First, install the required Python packages:

```bash
pip install -r req.txt
```

### 2. Configure Admin Credentials (per experiment)

Each experiment has credentials at: `experiments/<experiment>/admin_credentials.json`.

Recommended (hashed) format:

```
{
  "username": "admin",
  "password_hash": "<hex>",
  "salt": "<hex>",
  "iterations": 240000,
  "algorithm": "pbkdf2_sha256"
}
```

Legacy plaintext is still accepted and will be hashed in-memory:

```
{ "username": "admin", "password": "password" }
```

You can override with environment variables `ADMIN_USERNAME` and `ADMIN_PASSWORD` (useful for development). These are hashed in-memory at startup.

Example:

```
export ADMIN_USERNAME=admin
export ADMIN_PASSWORD=change-me
```

Note: The default dev creds are `admin` / `password`. Change these in production.

### 3. Run the Server

Start the FastAPI server from the repository root (recommended):

```bash
uvicorn server.rpc_server:app --host 0.0.0.0 --port 9000
```

Root APIs bind to a default experiment (preferred name: `experiments/default`).
You can select which experiment powers the root endpoints via `DEFAULT_EXPERIMENT`.

Examples:

```
# Use the renamed default experiment directory
export DEFAULT_EXPERIMENT=default

# or, fall back to the legacy name
export DEFAULT_EXPERIMENT=default_experiment
```

Endpoints at root include: `/functions`, `/call`, `/logs`, `/log-options`, and admin endpoints under `/admin/*`.
Per-experiment apps are served under `/exp/<experiment>/...`.

Dynamic experiments
-------------------
- You can add new experiment folders under `experiments/<name>` at any time. Each experiment must have this structure:
  - `db/students.db` (created on first run),
  - `funcs/*.py` (instructor functions),
  - `ui/` (HTML dashboard/pages),
  - `admin_credentials.json` (experiment’s admin login).
- Launching a new experiment from the landing page mounts it dynamically without restarting the server.

Health
------
- Check server health and status: `GET /api/health` → `{ ok, active, version }`.

Quick Guide (Launch + Access)
-----------------------------
- Launch an experiment:
  1) Open `http://localhost:9000/` and click Launch for `<experiment>`.
  2) Inline login prompts for credentials from `experiments/<experiment>/admin_credentials.json`.
  3) On success, the row shows Active. Click “Open UI” to open `/exp/<experiment>/ui/dashboard.html` in a new tab.
- Access model:
  - Dashboard: visible without login (shows auth badge and Login/Logout).
  - Students: requires login; shows a message if not authenticated.
  - Logs: read-only, public when active; shows a message if not active.
  - Random Actions: public; requires active experiment and a registered `student_id`.
- Admin API examples (per experiment):
  - Login: `POST /exp/<experiment>/admin/login` with `{ "username": "...", "password": "..." }` (JSON or form-encoded).
  - List students: `GET /exp/<experiment>/admin/students` (requires login + active experiment).
  - Add student: `POST /exp/<experiment>/admin/add-student` with `{ "student_id": "s001", "name": "Alice" }`.
  - Delete student: `DELETE /exp/<experiment>/admin/student/s001`.
  - Delete a student's logs: `DELETE /exp/<experiment>/admin/logs/student/s001`.
  - Reload functions from `funcs/`: `POST /exp/<experiment>/admin/reload-functions`.
  - View logs (public): `GET /exp/<experiment>/logs?n=100`.

  Root equivalents (bound to `DEFAULT_EXPERIMENT`): use the same paths without `/exp/<experiment>`, e.g. `DELETE /admin/logs/student/s001`.

Client notes
------------
- Students call the root endpoints (`/functions`, `/call`, `/logs`). Calls use the currently active experiment on the server — no need to send the experiment name from the client.
- Tag runs with `trial` (formerly `experiment`). The server stores this tag under `experiment_name` in the DB for compatibility.
- Check registration: `GET /is-registered?student_id=<id>` returns `{ registered: true|false }`.

Logs and Filters
----------------
- Endpoints:
  - Root: `GET /logs`
  - Per-experiment: `GET /exp/<experiment>/logs`
- Filters (query params):
  - Student: `student_id` or `sid`
  - Trial tag: `trial` or `trial_name` (legacy: `experiment` or `exp`)
  - Time range: `start_time`, `end_time` as ISO 8601 (e.g., `2025-09-07T01:23:45Z`)
  - Limit/order: `n` (1–1000), `order` = `latest` | `earliest`
- Options endpoint: `GET /log-options` returns `{ students, experiments, trials }` to help build filters.
- Admin-only list (requires login + active): `GET /admin/logs` (root or under `/exp/<experiment>`), accepts the same filters.

Examples:

```bash
# Root logs filtered by student + trial
curl 'http://localhost:9000/logs?sid=s001&trial_name=bisection-demo&n=50&order=latest'

# Per-experiment logs filtered by time window
curl 'http://localhost:9000/exp/default/logs?start_time=2025-09-07T00:00:00Z&end_time=2025-09-07T02:00:00Z'
```

### 4. Register a Student

Admin endpoints require a login session. Use the web UI or login via curl and reuse the session cookie.

- Option A: Use the UI
  1) Open `http://localhost:9000/`, click Launch for your experiment, and login when prompted (or visit `http://localhost:9000/ui/login.html` for the default experiment).
  2) Go to the Dashboard → Student Management to add a student.

- Option B: Use curl with cookies

```bash
# 1) Login and save session cookie
curl -sS -c cookies.txt -X POST -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"password"}' \
  http://localhost:9000/admin/login

# 2) Add a student (name required, email optional)
curl -sS -b cookies.txt -X POST -H "Content-Type: application/json" \
  -d '{"student_id":"s001","name":"Alice","email":"alice@example.com"}' \
  http://localhost:9000/admin/add-student
```

### 5. Run the Client

The `client/client.py` file contains an example of how a student would interact with the server. It lists available functions and calls a few for demonstration.

```bash
python client/client.py
```

### 7. View the Dashboard

- Admin UI: open `http://localhost:9000/ui/login.html`, then use the Dashboard to access Student Management and Log Visualization. When launching from the landing page, experiment-specific UIs live under `/exp/<experiment>/ui/...` and automatically scope API calls to that experiment.

- Optional Marimo demo: there is a stub at `server/demo.py` you can open with `marimo edit server/demo.py`. If you use it, ensure it connects to the correct DB path (`db/students.db`).

## How It Works

### For Instructors: Adding New Functions

Place Python files with public functions in the `experiments/<experiment_name>/funcs/` folder. Any function that does not start with an underscore `_` is automatically loaded by the server on startup and exposed to clients. You can change the folder with the `FUNCTIONS_DIR` environment variable.

**Example:** Adding a simple cubic function to `funcs/functions.py`.

```python
# in funcs/functions.py

def cubic(x: float) -> float:
    """Return x^3."""
    return x * x * x
```

### For Students: Using the Client

Students can use the `client/client.py` script as a template. They need to:
1.  Set their `STUDENT_ID` at the top of the script.
2.  Optionally set a `TRIAL` name/ID to tag their calls (e.g., "bisection-demo").
3.  Use the `client` object to call any of the functions provided by the instructor.
4.  The `client.help()` method can be used to list all available functions and their signatures.

```python
# in client/client.py

SERVER_URL = "http://localhost:9000"
STUDENT_ID = "s001" # Change to your assigned ID
TRIAL = "bisection-demo"  # Optional trial label

client = RPCClient(server_url=SERVER_URL, student_id=STUDENT_ID, trial_name=TRIAL)

# Get a list of available functions
client.help()

# Call a function (raises on error). Each call is logged with student_id and trial.
try:
    result = client.square(7)
    print(f"Result: {result}")
except Exception as e:
    print(f"RPC error: {e}")
```

The client raises exceptions on failures (network/server/protocol) using `RPCError` subtypes. Logs include `student_id` and a `trial` tag (stored under `experiment_name` in the DB for compatibility).

Compatibility note: The server still accepts the deprecated `experiment` parameter on `/call` and log filters; prefer the new `trial`/`trial_name` parameters going forward.
