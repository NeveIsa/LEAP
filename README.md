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

### 2. Run the Server

Navigate to the `server` directory and start the FastAPI server with Uvicorn.

```bash
cd server
uvicorn rpc_server:app --host 0.0.0.0 --port 9000
```

The server is now running and listening on port 9000.

### 3. Register a Student

Before a student can use the system, they must be registered. You can add a student using a simple `curl` command.

```bash
# Register a student with the ID "s001"
curl -X POST -H "Content-Type: application/json" -d '{"student_id": "s001"}' http://localhost:9000/admin/add-student
```

### 4. Run the Client

The `client/client.py` file contains an example of how a student would interact with the server. It lists available functions and calls a few for demonstration.

```bash
python client/client.py
```

### 5. View the Dashboard

The project includes a `demo.py` Marimo notebook that serves as the starting point for a dashboard. To run it:

```bash
cd server
marimo edit demo.py
```

This will open a new tab in your browser with the interactive dashboard.

## How It Works

### For Instructors: Adding New Functions

To add a new function for students to use, simply define it in the `server/functions.py` file. Any standard Python function that does not start with an underscore `_` will be automatically loaded by the server on startup and exposed to the clients.

**Example:** Adding a simple cubic function to `server/functions.py`.

```python
# in server/functions.py

def cubic(x: float) -> float:
    """Return x^3."""
    return x * x * x
```

### For Students: Using the Client

Students can use the `client/client.py` script as a template. They need to:
1.  Set their `STUDENT_ID` at the top of the script.
2.  Use the `client` object to call any of the functions provided by the instructor.
3.  The `client.help()` method can be used to list all available functions and their signatures.

```python
# in client/client.py

SERVER_URL = "http://localhost:9000"
STUDENT_ID = "s001" # Change to your assigned ID

client = RPCClient(server_url=SERVER_URL, student_id=STUDENT_ID)

# Get a list of available functions
client.help()

# Call a function
result = client.square(7)
print(f"Result: {result}")
```