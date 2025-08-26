# rpc_server.py
from fastapi import FastAPI, HTTPException, Query, Depends, status, Request, Response
from fastapi.staticfiles import StaticFiles
from starlette.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
from typing import Any, Callable, Dict, Optional, Literal
from starlette.middleware.sessions import SessionMiddleware
import importlib.util
import inspect
import json
import os
import glob
import sys
import datetime

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Swap in ORM-based storage (SQLAlchemy + duckdb-engine)
import storage_orm as storage

_current_dir = os.path.dirname(os.path.abspath(__file__))
# Resolve repo root and default functions dir at project root
_project_root = os.path.dirname(_current_dir)
FUNCTIONS_DIR = os.environ.get("FUNCTIONS_DIR", os.path.join(_project_root, "funcs"))
storage.init_db()

FUNCTION_REGISTRY: Dict[str, Callable[..., Any]] = {}

def load_functions_from_directory(directory: str) -> Dict[str, Callable[..., Any]]:
    """Dynamically loads all public functions from .py files in a directory."""
    funcs = {}
    # Use glob to find all python files in the specified directory
    for filepath in glob.glob(os.path.join(directory, "*.py")):
        module_name = os.path.splitext(os.path.basename(filepath))[0]
        # To avoid conflicts, create a unique spec name
        spec = importlib.util.spec_from_file_location(f"funcs.{module_name}", filepath)
        if spec and spec.loader:
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            for name, obj in vars(mod).items():
                if name.startswith("_"):
                    continue
                if inspect.isfunction(obj):
                    if name in funcs:
                        print(f"Warning: Function '{name}' is being redefined.")
                    funcs[name] = obj
    if not funcs:
        print(f"Warning: No public functions found in directory '{directory}'.")
    return funcs

def register_all_functions():
    """Registers all functions from the configured directory."""
    global FUNCTION_REGISTRY
    FUNCTION_REGISTRY = load_functions_from_directory(FUNCTIONS_DIR)

register_all_functions()

class CallRequest(BaseModel):
    student_id: str
    func_name: str
    args: list[Any] = []
    experiment: Optional[str] = None

app = FastAPI(title="Classroom RPC Server", version="0.4.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*", "null"],  # Allows all origins, including file://
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

app.mount("/ui", StaticFiles(directory=os.path.join(_current_dir, "ui")), name="ui")

# Mount marimo notebooks directory
marimo_dir = os.path.join(_project_root, "marimo-viz")
if os.path.exists(marimo_dir):
    app.mount("/marimo", StaticFiles(directory=marimo_dir), name="marimo")

# Add route to serve marimo notebook as HTML
@app.get("/marimo-embed/{notebook_name}")
async def serve_marimo_notebook(notebook_name: str):
    """Serve a marimo notebook as an embedded HTML page"""
    notebook_path = os.path.join(marimo_dir, f"{notebook_name}.py")
    
    if not os.path.exists(notebook_path):
        raise HTTPException(status_code=404, detail=f"Notebook {notebook_name}.py not found")
    
    # Read the notebook content
    with open(notebook_path, 'r', encoding='utf-8') as f:
        notebook_content = f.read()
    
    # Create a simple HTML page that embeds the notebook
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Marimo Notebook - {notebook_name}</title>
        <style>
            body {{
                margin: 0;
                padding: 20px;
                background: #1a1a1a;
                color: #e0e0e0;
                font-family: 'Inter', sans-serif;
            }}
            .notebook-container {{
                max-width: 1200px;
                margin: 0 auto;
                background: #2d2d2d;
                border-radius: 8px;
                padding: 20px;
                border: 1px solid #444;
            }}
            .code-block {{
                background: #1a1a1a;
                border: 1px solid #444;
                border-radius: 4px;
                padding: 15px;
                margin: 10px 0;
                font-family: 'Courier New', monospace;
                white-space: pre-wrap;
                color: #e0e0e0;
            }}
            .output {{
                background: #2a2a2a;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 10px;
                margin: 5px 0;
                color: #b0b0b0;
            }}
        </style>
    </head>
    <body>
        <div class="notebook-container">
            <h1>Marimo Notebook: {notebook_name}</h1>
            <p>This is a static view of the notebook. For interactive execution, you would need to run a marimo server.</p>
            
            <h2>Notebook Content:</h2>
            <div class="code-block">{notebook_content}</div>
            
            <h2>To run this notebook interactively:</h2>
            <div class="output">
                <p>1. Install marimo: pip install marimo</p>
                <p>2. Run the notebook: marimo run {notebook_name}.py</p>
                <p>3. Open the URL shown in the terminal</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return Response(content=html_content, media_type="text/html")

@app.get("/")
async def root_redirect(request: Request):
    # Auth landing: dashboard if logged in, else login page
    if request.session.get("authenticated"):
        return RedirectResponse(url="/ui/dashboard.html")
    return RedirectResponse(url="/ui/login.html")

# --- Public registration check ---
@app.get("/is-registered")
def is_registered(student_id: str = Query(..., description="Student ID to check")):
    """Public endpoint to check if a student_id is registered.

    Returns {"registered": bool} without logging any event. This is intended to let
    clients preflight their student_id without requiring admin access or creating logs.
    """
    try:
        return {"registered": storage.student_exists(student_id)}
    except Exception:
        # On storage issues, respond gracefully as unregistered
        return {"registered": False}

# --- Session Middleware ---
SESSION_SECRET_KEY = os.environ.get("SESSION_SECRET_KEY", "super-secret-key-please-change-me-in-prod")
# Session cookie expires when browser closes (no Max-Age/Expires)
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET_KEY, max_age=None)
# --------------------------

# --- Admin Authentication ---
def _load_admin_credentials() -> tuple[str, str]:
    """Load admin credentials from env or JSON file.

    Priority:
    1) Environment variables: ADMIN_USERNAME, ADMIN_PASSWORD
    2) JSON credentials file at path ADMIN_CREDENTIALS_FILE or ./admin_credentials.json
    3) Fallback defaults (admin / password)
    """
    # 1) Env vars override all
    env_user = os.environ.get("ADMIN_USERNAME")
    env_pass = os.environ.get("ADMIN_PASSWORD")
    if env_user and env_pass:
        return env_user, env_pass

    # 2) JSON credentials file
    cred_path = os.environ.get(
        "ADMIN_CREDENTIALS_FILE",
        os.path.join(_current_dir, "admin_credentials.json"),
    )
    try:
        if os.path.isfile(cred_path):
            with open(cred_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                username = data.get("username") or data.get("user")
                password = data.get("password") or data.get("pass")
                if username and password:
                    return username, password
    except Exception:
        # Ignore file errors and fall back
        pass

    # 3) Fallback defaults
    return ("admin", "password")

ADMIN_USERNAME, ADMIN_PASSWORD = _load_admin_credentials()

class LoginRequest(BaseModel):
    username: str
    password: str

@app.post("/admin/login")
async def login(request: Request, login_data: LoginRequest):
    if login_data.username == ADMIN_USERNAME and login_data.password == ADMIN_PASSWORD:
        request.session["authenticated"] = True
        return {"message": "Login successful"}
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

def is_admin_authenticated(request: Request):
    if not request.session.get("authenticated"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return True
# ----------------------------

@app.post("/admin/logout")
async def logout(request: Request, response: Response):
    """Clear session and remove cookie to log out admin."""
    request.session.clear()
    response.delete_cookie("session")
    return {"message": "Logged out"}

@app.get("/admin/ping")
async def admin_ping(authenticated: bool = Depends(is_admin_authenticated)):
    """Quick auth check; returns 401 if not authenticated."""
    return {"ok": True}

@app.get("/functions")
def list_functions():
    return {
        name: {
            "signature": str(inspect.signature(fn)),
            "doc": (fn.__doc__ or "").strip()
        }
        for name, fn in FUNCTION_REGISTRY.items()
    }

@app.post("/call")
def call_function(req: CallRequest):
    if req.func_name not in FUNCTION_REGISTRY:
        raise HTTPException(status_code=404, detail=f"Function '{req.func_name}' not found")
    if not storage.student_exists(req.student_id):
        raise HTTPException(status_code=403, detail=f"Invalid student ID '{req.student_id}'")

    fn = FUNCTION_REGISTRY[req.func_name]

    def _enc(o):
        try:
            return json.dumps(jsonable_encoder(o))
        except Exception:
            return json.dumps(repr(o))

    try:
        result = fn(*req.args)
        storage.log_event(
            student_id=req.student_id,
            experiment_name=req.experiment,
            func_name=req.func_name,
            args_json=_enc(req.args),
            result_json=_enc(result),
            error=None,
        )
    except Exception as e:
        storage.log_event(
            student_id=req.student_id,
            experiment_name=req.experiment,
            func_name=req.func_name,
            args_json=_enc(req.args),
            result_json=None,
            error=str(e),
        )
        raise HTTPException(status_code=400, detail=f"Function execution error: {e}")

    return {"result": jsonable_encoder(result)}

@app.get("/healthz")
def healthz():
    return {"status": "ok", "registered_functions": list(FUNCTION_REGISTRY.keys())}

class AddStudentBody(BaseModel):
    student_id: str
    name: str
    email: Optional[str] = None

@app.post("/admin/add-student")
def add_student(body: AddStudentBody, authenticated: bool = Depends(is_admin_authenticated)):
    storage.add_student(student_id=body.student_id, name=body.name, email=body.email)
    return {"status": "ok"}

@app.get("/admin/students")
def list_all_students(authenticated: bool = Depends(is_admin_authenticated)):
    """Returns a list of all registered student IDs."""
    return {"students": storage.list_students()}

@app.delete("/admin/student/{student_id}", status_code=200)
def remove_student(student_id: str, authenticated: bool = Depends(is_admin_authenticated)):
    """Deletes a student and all of their associated logs."""
    was_deleted = storage.delete_student(student_id)
    if not was_deleted:
        raise HTTPException(status_code=404, detail=f"Student ID '{student_id}' not found.")
    return {"status": "ok", "message": f"Student '{student_id}' and all associated logs have been deleted."}

@app.get("/admin/logs")
def get_server_logs(
    student_id: Optional[str] = Query(None, description="Optional: Filter logs by student ID."),
    experiment_name: Optional[str] = Query(None, description="Optional: Filter logs by experiment name."),
    n: int = Query(100, ge=1, le=1000, description="Number of logs to return"),
    order: Literal["latest", "earliest"] = Query("latest", description="Ordering by timestamp"),
    authenticated: bool = Depends(is_admin_authenticated)
):
    """Returns up to N log events, optionally filtered and ordered."""
    try:
        logs = storage.fetch_logs(student_id=student_id, experiment_name=experiment_name, n=n, order=order)
        return {"logs": logs}
    except Exception:
        # If logs table or DB isn't ready yet, return an empty list gracefully
        return {"logs": []}

# Public logs endpoint (no admin auth)
@app.get("/logs")
def get_logs(
    student_id: Optional[str] = Query(None, description="Optional: Filter logs by student ID. Alias: sid"),
    experiment_name: Optional[str] = Query(None, description="Optional: Filter logs by experiment name. Alias: exp"),
    sid: Optional[str] = Query(None, description="Alias for student_id"),
    exp: Optional[str] = Query(None, description="Alias for experiment_name"),
    n: int = Query(100, ge=1, le=1000, description="Number of logs to return"),
    order: Literal["latest", "earliest"] = Query("latest", description="Ordering by timestamp"),
    start_time: Optional[datetime.datetime] = Query(None, description="ISO 8601 format"),
    end_time: Optional[datetime.datetime] = Query(None, description="ISO 8601 format"),
):
    """Public endpoint: Returns logs, optionally filtered and ordered.

    Supports both `student_id`/`experiment_name` and their short aliases `sid`/`exp`.
    """
    try:
        eff_student = student_id or sid
        eff_experiment = experiment_name or exp
        logs = storage.fetch_logs(
            student_id=eff_student, 
            experiment_name=eff_experiment, 
            n=n, 
            order=order,
            start_time=start_time,
            end_time=end_time,
        )
        return {"logs": logs}
    except Exception:
        # If the table doesn't exist yet or DB not initialized, return empty
        return {"logs": []}

# Public endpoint to get distinct students/experiments for UI filters
@app.get("/log-options")
def get_log_options():
    try:
        students = storage.distinct_students_with_logs()
        experiments = storage.distinct_experiments()
        return {"students": students, "experiments": experiments}
    except Exception:
        return {"students": [], "experiments": []}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("rpc_server:app", host="0.0.0.0", port=9000, reload=False)
