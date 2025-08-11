# Interactive Classroom for Numerical Methods

This project provides a client-server framework for teaching numerical optimization and root-finding techniques. Students use a client to remotely call and test mathematical functions. The server executes the functions, logs every attempt to a database, and provides a foundation for a real-time dashboard to visualize student progress.

## Features

- **JSON-RPC Style API Server**: A robust server built with FastAPI that exposes numerical functions.
- **Dynamic Function Loading**: Instructors can add new Python functions on the fly, and the server automatically makes them available to students.
- **Persistent Logging**: Logs all student submissions (arguments, results, and errors) to a local DuckDB database.
- **Simple Student Client**: An intuitive Python client that abstracts away API calls, allowing students to call remote functions as if they were local.
- **SQLAlchemy ORM**: Clean and robust database interaction layer.
- **Dashboard Ready**: Includes a Marimo notebook to easily build a real-time monitoring dashboard.

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

### 2. Configure Admin Credentials (optional)

Admin login credentials are read from a JSON file by default: `server/admin_credentials.json`.

File format:

```
{
  "username": "admin",
  "password": "password"
}
```

You can override the file location with `ADMIN_CREDENTIALS_FILE` or use environment variables `ADMIN_USERNAME` and `ADMIN_PASSWORD` to take precedence over the file.

Example:

```
export ADMIN_USERNAME=admin
export ADMIN_PASSWORD=change-me
```

### 3. Run the Server

Start the FastAPI server from the repository root (recommended):

```bash
uvicorn server.rpc_server:app --host 0.0.0.0 --port 9000
```

The server loads instructor functions from `./funcs` by default. You can override this with `FUNCTIONS_DIR=/path/to/dir`.

The server is now running and listening on port 9000.

### 4. Register a Student

Admin endpoints require a login session. Use the web UI or login via curl and reuse the session cookie.

- Option A: Use the UI
  1) Open `http://localhost:9000/ui/login.html` and login (default: `admin` / `password`).
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

### 6. View the Dashboard

- Admin UI: open `http://localhost:9000/ui/login.html`, then use the Dashboard to access Student Management and Log Visualization.
- Log Visualization: `ui/viz/lineplot.html` renders the last 100 logs using uPlot. Series are colored by student. It uses the public endpoint `GET /logs`.
- Optional Marimo demo: there is a stub at `server/demo.py` you can open with `marimo edit server/demo.py`. If you use it, ensure it connects to the correct DB path (`db/students.db`).

## How It Works

### For Instructors: Adding New Functions

Place Python files with public functions in the repository-level `funcs/` folder (default). Any function that does not start with an underscore `_` is automatically loaded by the server on startup and exposed to clients. You can change the folder with the `FUNCTIONS_DIR` environment variable.

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
2.  Optionally set an `EXPERIMENT` name to tag their calls (e.g., "bisection-demo").
3.  Use the `client` object to call any of the functions provided by the instructor.
4.  The `client.help()` method can be used to list all available functions and their signatures.

```python
# in client/client.py

SERVER_URL = "http://localhost:9000"
STUDENT_ID = "s001" # Change to your assigned ID
EXPERIMENT = "bisection-demo"  # Optional experiment label

client = RPCClient(server_url=SERVER_URL, student_id=STUDENT_ID, experiment_name=EXPERIMENT)

# Get a list of available functions
client.help()

# Call a function (raises on error). Each call is logged with student_id and experiment.
try:
    result = client.square(7)
    print(f"Result: {result}")
except Exception as e:
    print(f"RPC error: {e}")
```

The client raises exceptions on failures (network/server/protocol) using `RPCError` subtypes. Logs now include `student_id` and `experiment_name` for each call.
```
