
# rpc_server.py
from fastapi import FastAPI, HTTPException, Query, Depends, status, Request, Response, Body
import logging
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, validator, Field
from typing import Any, Callable, Dict, List, Optional, Literal
import re
from starlette.middleware.sessions import SessionMiddleware
import secrets
import inspect
import json
import os
import sys
import datetime

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from .storage_orm import Storage  # when imported as package (server.rpc_server)
    from .utils import (
        enc as _enc,
        resolve_log_filters as _resolve_log_filters,
        load_functions_from_directory as _load_functions_from_directory,
        load_admin_credentials as _load_admin_credentials_from_path,
        NoCacheHTMLMiddleware,
        build_experiment_app,
    )
except ImportError:  # pragma: no cover
    from storage_orm import Storage  # when executed as script
    from utils import (
        enc as _enc,
        resolve_log_filters as _resolve_log_filters,
        load_functions_from_directory as _load_functions_from_directory,
        load_admin_credentials as _load_admin_credentials_from_path,
        NoCacheHTMLMiddleware,
        build_experiment_app,
    )

_current_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_current_dir)
APP_VERSION = "0.1.0"

# Security validation utilities
def _validate_safe_string(value: str, max_length: int = 255, allow_empty: bool = False) -> str:
    """Validate that string inputs are safe and reasonable."""
    if not allow_empty and not value:
        raise ValueError("Value cannot be empty")
    if len(value) > max_length:
        raise ValueError(f"Value too long (max {max_length} characters)")
    # Check for basic injection patterns
    dangerous_patterns = [
        r'[;<>&|`$]',  # Shell metacharacters
        r'__[a-zA-Z_]+__',  # Python dunder methods
        r'eval|exec|import|__import__|open|file',  # Dangerous Python keywords
    ]
    for pattern in dangerous_patterns:
        if re.search(pattern, value, re.IGNORECASE):
            raise ValueError(f"Invalid characters or patterns detected")
    return value

def _validate_function_args(args: list[Any], max_args: int = 10, max_depth: int = 5) -> list[Any]:
    """Validate function arguments for safety."""
    if len(args) > max_args:
        raise ValueError(f"Too many arguments (max {max_args})")
    
    def check_value(obj, depth=0):
        if depth > max_depth:
            raise ValueError("Nested data too deep")
        if isinstance(obj, str):
            if len(obj) > 10000:  # Prevent extremely long strings
                raise ValueError("String argument too long")
        elif isinstance(obj, (list, tuple)):
            if len(obj) > 1000:  # Prevent huge lists
                raise ValueError("List argument too long")
            for item in obj:
                check_value(item, depth + 1)
        elif isinstance(obj, dict):
            if len(obj) > 100:  # Prevent huge dicts
                raise ValueError("Dict argument too large")
            for key, value in obj.items():
                check_value(key, depth + 1)
                check_value(value, depth + 1)
        elif obj is not None and not isinstance(obj, (int, float, bool)):
            raise ValueError(f"Unsupported argument type: {type(obj)}")
    
    for arg in args:
        check_value(arg)
    return args

# Use a single session secret across root and mounted experiment apps
def _get_session_secret() -> str:
    """Get session secret from environment or generate secure default."""
    env_secret = os.environ.get("SESSION_SECRET_KEY")
    if env_secret:
        return env_secret
    
    # Generate cryptographically secure secret for development
    secure_default = secrets.token_hex(32)  # 256-bit key
    print("🔐 Generated secure session secret for this session.")
    print("⚠️  For production, set SESSION_SECRET_KEY environment variable!")
    return secure_default

SESSION_SECRET_KEY = _get_session_secret()
# Rotate runtime secret each start to invalidate old sessions
_STARTUP_NONCE = secrets.token_hex(16)
_DERIVED_SESSION_SECRET = f"{SESSION_SECRET_KEY}:{_STARTUP_NONCE}"
logging.info("Session secret rotated at startup; previous sessions invalidated.")
SESSION_KW = dict(max_age=7*24*3600, same_site="lax", https_only=False, path="/")

# Import state management
from .state import server_state as _server_state

# Import shared utilities instead of duplicating
from .utils import enc as _enc, resolve_log_filters as _resolve_log_filters

def _invoke_and_log(
    *, storage: Storage, fn: Callable[..., Any], func_name: str,
    args: list[Any], student_id: str, trial: Optional[str],
):
    """Invoke function and persist result/error to storage."""
    try:
        result = fn(*args)
        storage.log_event(
            student_id=student_id,
            experiment_name=_server_state.get_active_experiment(),
            trial=trial,
            func_name=func_name,
            args_json=_enc(args),
            result_json=_enc(result),
            error=None,
        )
        return result
    except Exception as e:
        storage.log_event(
            student_id=student_id,
            experiment_name=_server_state.get_active_experiment(),
            trial=trial,
            func_name=func_name,
            args_json=_enc(args),
            result_json=None,
            error=str(e),
        )
        raise

def create_experiment_app(experiment_name: str) -> FastAPI:
    experiment_dir = os.path.join(_project_root, "experiments", experiment_name)
    if not os.path.isdir(experiment_dir):
        return None

    db_path = os.path.join(experiment_dir, "db/students.db")
    if not os.path.exists(db_path):
        logging.info("Database file not found at %s. A new one will be created.", db_path)
    funcs_dir = os.path.join(experiment_dir, "funcs")
    ui_dir = os.path.join(experiment_dir, "ui")
    logging.debug("Creating app for experiment '%s' with db_path: %s", experiment_name, db_path)
    storage = Storage(db_path)

    function_registry: Dict[str, Callable[..., Any]] = _load_functions_from_directory(funcs_dir)

    def reload_functions() -> int:
        nonlocal function_registry
        new_funcs = _load_functions_from_directory(funcs_dir)
        function_registry = new_funcs
        return len(function_registry)

    app = FastAPI(title=f"Experiment: {experiment_name}")

    app.mount("/ui", StaticFiles(directory=ui_dir), name="ui")

    # IMPORTANT: add SessionMiddleware to the experiment app as well, so its
    # /admin/* endpoints can persist authentication cookies correctly. Parent
    # middleware does not wrap mounted sub-apps in Starlette.
    app.add_middleware(SessionMiddleware, secret_key=_DERIVED_SESSION_SECRET, **SESSION_KW)

    # Use global admin credentials
    ADMIN_USERNAME, ADMIN_PASSWORD = _load_admin_credentials_from_path()

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

    @app.post("/admin/logout")
    async def logout(request: Request, response: Response):
        request.session.clear()
        response.delete_cookie("session")
        return {"message": "Logged out"}

    def _require_active_this_experiment():
        active = _server_state.get_active_experiment()
        if active is None:
            raise HTTPException(status_code=409, detail="No active experiment. Start it from the landing page.")
        if active != experiment_name:
            raise HTTPException(status_code=409, detail=f"Experiment '{active}' is active. Open that UI or stop it first.")
        return True

    # Combined dependency: require admin AND active experiment (per-experiment)
    def _require_admin_and_active(
        authenticated: bool = Depends(is_admin_authenticated),
        _active_ok: bool = Depends(_require_active_this_experiment),
    ):
        return True

    @app.get("/files")
    def list_files(ext: Optional[str] = Query(None), dir: Optional[str] = Query(None)):
        """List files in the experiment's UI directory.

        - Query params:
          - ext: optional file extension filter (e.g., "md" or ".md").
          - dir: optional subdirectory under UI (e.g., "quiz"). Single segment only.
        """
        files: list[str] = []
        try:
            norm_ext = None
            if ext:
                norm_ext = ext if ext.startswith(".") else f".{ext}"
                norm_ext = norm_ext.lower()
            base_dir = ui_dir
            if dir:
                # allow only a safe single-segment directory name to avoid traversal
                if not re.match(r"^[A-Za-z0-9_-]+$", dir or ""):
                    return {"files": []}
                cand = os.path.join(ui_dir, dir)
                if os.path.isdir(cand):
                    base_dir = cand
                else:
                    return {"files": []}
            for name in os.listdir(base_dir):
                if norm_ext:
                    if name.lower().endswith(norm_ext):
                        files.append(name)
                else:
                    files.append(name)
        except Exception:
            pass
        files.sort()
        return {"files": files}

    @app.post("/admin/reload-functions", dependencies=[Depends(is_admin_authenticated), Depends(_require_active_this_experiment)])
    def admin_reload_functions():
        count = reload_functions()
        return {"status": "ok", "functions": count}

    @app.get("/admin/ping")
    async def admin_ping(authenticated: bool = Depends(is_admin_authenticated)):
        return {"ok": True}

    @app.get("/functions")
    def list_functions():
        return {
            name: {
                "signature": str(inspect.signature(fn)),
                "doc": (fn.__doc__ or "").strip()
            }
            for name, fn in function_registry.items()
        }

    # Students list requires admin + active experiment
    @app.get("/students", dependencies=[Depends(is_admin_authenticated), Depends(_require_active_this_experiment)])
    def list_students_admin():
        return {"students": storage.list_students()}

    class CallRequest(BaseModel):
        student_id: str = Field(..., max_length=255)
        func_name: str = Field(..., max_length=255)
        args: list[Any] = []
        # New preferred name for tagging runs; kept 'experiment' for backward compatibility
        trial: Optional[str] = Field(None, max_length=255)
        experiment: Optional[str] = Field(None, max_length=255)
        # Explicit experiment context; must match active experiment for root calls
        experiment_name: Optional[str] = Field(None, max_length=255)

        @validator('student_id', 'func_name')
        def validate_required_strings(cls, v):
            return _validate_safe_string(v)
        
        @validator('trial', 'experiment', 'experiment_name')
        def validate_optional_strings(cls, v):
            if v is not None:
                return _validate_safe_string(v, allow_empty=True)
            return v
        
        @validator('args')
        def validate_args(cls, v):
            return _validate_function_args(v)

    @app.post("/call")
    def call_function(req: CallRequest):
        # Enforce experiment context: only allow calls when THIS experiment is active
        active = _server_state.get_active_experiment()
        if active is None:
            raise HTTPException(status_code=409, detail="No active experiment. Start one from the landing page.")
        if active != experiment_name:
            raise HTTPException(status_code=409, detail=f"Experiment '{active}' is active. Open that UI or stop it first.")
        if req.experiment_name and req.experiment_name != experiment_name:
            raise HTTPException(status_code=409, detail=f"Mismatched experiment context. Expected '{experiment_name}', got '{req.experiment_name}'.")
        if req.func_name not in function_registry:
            raise HTTPException(status_code=404, detail=f"Function '{req.func_name}' not found")
        if not storage.student_exists(req.student_id):
            raise HTTPException(status_code=403, detail=f"Invalid student ID '{req.student_id}'")

        fn = function_registry[req.func_name]

        trial_name = req.trial or req.experiment

        try:
            result = _invoke_and_log(
                storage=storage, fn=fn, func_name=req.func_name,
                args=req.args, student_id=req.student_id, trial=trial_name,
            )
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Function execution error: {e}")

        return {"result": jsonable_encoder(result)}

    class AddStudentBody(BaseModel):
        student_id: str
        name: str
        email: Optional[str] = None

    @app.post("/admin/add-student", dependencies=[Depends(is_admin_authenticated), Depends(_require_active_this_experiment)])
    def add_student(body: AddStudentBody):
        storage.add_student(student_id=body.student_id, name=body.name, email=body.email)
        return {"status": "ok"}

    class BulkAddStudentsBody(BaseModel):
        students: List[Dict[str, str]]

    @app.post("/admin/add-students-bulk", dependencies=[Depends(is_admin_authenticated), Depends(_require_active_this_experiment)])
    def add_students_bulk(body: BulkAddStudentsBody):
        """Bulk add students for efficient CSV uploads."""
        result = storage.add_students_bulk(body.students)
        return {"status": "ok", **result}

    @app.get("/admin/students", dependencies=[Depends(is_admin_authenticated), Depends(_require_active_this_experiment)])
    def list_all_students():
        return {"students": storage.list_students()}

    @app.delete("/admin/student/{student_id}", status_code=200, dependencies=[Depends(is_admin_authenticated), Depends(_require_active_this_experiment)])
    def remove_student(student_id: str):
        was_deleted = storage.delete_student(student_id)
        if not was_deleted:
            raise HTTPException(status_code=404, detail=f"Student ID '{student_id}' not found.")
        return {"status": "ok", "message": f"Student '{student_id}' and all associated logs have been deleted."}

    @app.get("/admin/logs", dependencies=[Depends(is_admin_authenticated), Depends(_require_active_this_experiment)])
    def get_server_logs(
        student_id: Optional[str] = Query(None),
        experiment_name: Optional[str] = Query(None),
        trial: Optional[str] = Query(None),
        n: int = Query(100, ge=1, le=10_000),
        order: Literal["latest", "earliest"] = Query("latest"),
    ):
        eff_trial = trial or experiment_name
        logs = storage.fetch_logs(student_id=student_id, experiment_name=eff_trial, n=n, order=order)
        return {"logs": logs}

    @app.get("/logs")
    def get_logs(
        student_id: Optional[str] = Query(None),
        experiment_name: Optional[str] = Query(None),
        sid: Optional[str] = Query(None),
        exp: Optional[str] = Query(None),
        trial: Optional[str] = Query(None),
        trial_name: Optional[str] = Query(None),
        n: int = Query(100, ge=1, le=10_000),
        order: Literal["latest", "earliest"] = Query("latest"),
        start_time: Optional[datetime.datetime] = Query(None),
        end_time: Optional[datetime.datetime] = Query(None),
        _active_ok: bool = Depends(_require_active_this_experiment),
    ):
        eff_student, eff_experiment = _resolve_log_filters(
            student_id=student_id, sid=sid,
            experiment_name=experiment_name, exp=exp,
            trial=trial, trial_name=trial_name,
        )
        logs = storage.fetch_logs(
            student_id=eff_student, 
            experiment_name=eff_experiment, 
            n=n, 
            order=order,
            start_time=start_time,
            end_time=end_time,
        )
        return {"logs": logs}

    @app.get("/log-options")
    def get_log_options():
        students = storage.distinct_students_with_logs()
        experiments = storage.distinct_experiments()
        return {"students": students, "experiments": experiments, "trials": experiments}

    return app

# Override with factory-based implementation for simplicity and consistency.
def create_experiment_app(experiment_name: str) -> FastAPI:  # type: ignore[no-redef]
    return build_experiment_app(
        experiment_name=experiment_name,
        project_root=_project_root,
        session_secret=_DERIVED_SESSION_SECRET,
        session_cookie_opts=SESSION_KW,
        current_active=_server_state.get_active_experiment,
        invoke_and_log=_invoke_and_log,
    )

app = FastAPI(title="Classroom RPC Server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*", "null"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(SessionMiddleware, secret_key=_DERIVED_SESSION_SECRET, **SESSION_KW)

app.add_middleware(NoCacheHTMLMiddleware)

# Guard root-mounted UI (default experiment) so it's only reachable when that
# same experiment is active. Otherwise redirect to landing.
class _RootUIGuard(BaseHTTPMiddleware):
    def __init__(self, app, *, get_active: callable, get_default: callable):
        super().__init__(app)
        self._get_active = get_active
        self._get_default = get_default

    async def dispatch(self, request, call_next):
        try:
            path = request.url.path or ''
            if path.startswith('/ui') or path.startswith('/static'):
                active = self._get_active()
                default = self._get_default()
                if default and active != default:
                    from starlette.responses import RedirectResponse
                    return RedirectResponse(url='/', status_code=307)
        except Exception:
            pass
        return await call_next(request)

def _get_active_name():
    return _ACTIVE_EXPERIMENT

def _get_default_name():
    return _DEFAULT_EXPERIMENT

app.add_middleware(_RootUIGuard, get_active=_get_active_name, get_default=_get_default_name)

_experiments_dir = os.path.join(_project_root, "experiments")

# Discover experiments
_available_experiments = [
    d for d in os.listdir(_experiments_dir)
    if os.path.isdir(os.path.join(_experiments_dir, d))
] if os.path.isdir(_experiments_dir) else []

# Choose default experiment for root-level APIs/UI
_DEFAULT_EXPERIMENT = os.environ.get("DEFAULT_EXPERIMENT")
if not _DEFAULT_EXPERIMENT or _DEFAULT_EXPERIMENT not in _available_experiments:
    if "default" in _available_experiments:
        _DEFAULT_EXPERIMENT = "default"
    elif "default_experiment" in _available_experiments:
        _DEFAULT_EXPERIMENT = "default_experiment"
    elif _available_experiments:
        _DEFAULT_EXPERIMENT = _available_experiments[0]
    else:
        _DEFAULT_EXPERIMENT = None

if _DEFAULT_EXPERIMENT:
    _default_exp_dir = os.path.join(_experiments_dir, _DEFAULT_EXPERIMENT)
    _default_db_path = os.path.join(_default_exp_dir, "db/students.db")
    _default_funcs_dir = os.path.join(_default_exp_dir, "funcs")
    _default_ui_dir = os.path.join(_default_exp_dir, "ui")
    logging.info("Discovered default context: '%s' (UI binds here). Root APIs operate on the active experiment.", _DEFAULT_EXPERIMENT)

    _default_storage = Storage(_default_db_path)
    _default_function_registry: Dict[str, Callable[..., Any]] = _load_functions_from_directory(_default_funcs_dir)
    # Use global admin credentials instead of per-experiment credentials
    _DEFAULT_ADMIN_USERNAME, _DEFAULT_ADMIN_VERIFY = _load_admin_credentials_from_path()
else:
    _default_ui_dir = os.path.join(_project_root, "experiments", "default", "ui")
    _default_storage = None
    _default_function_registry = {}
    # Use global admin credentials
    _DEFAULT_ADMIN_USERNAME, _DEFAULT_ADMIN_VERIFY = _load_admin_credentials_from_path()

# Removed root-mounted /ui and /static; use canonical /exp/<experiment>/ui only.

@app.get("/")
async def read_index():
    return FileResponse(os.path.join(_current_dir, 'landing/index.html'))

@app.get("/login")
async def read_login():
    return FileResponse(os.path.join(_current_dir, 'landing/login.html'))

@app.get("/api/experiments")
def list_experiments():
    experiments_dir = os.path.join(_project_root, "experiments")
    if not os.path.isdir(experiments_dir):
        return []
    return [d for d in os.listdir(experiments_dir) if os.path.isdir(os.path.join(experiments_dir, d))]

@app.get("/api/active-experiment")
def get_active_experiment():
    return {"active": _server_state.get_active_experiment()}

@app.get("/api/health")
def health():
    return {"ok": True, "active": _server_state.get_active_experiment(), "version": APP_VERSION}

class _StartExperimentBody(BaseModel):
    name: str

# Require root admin auth for starting/stopping experiments
def _require_root_admin_for_api(request: Request):
    if not request.session.get("authenticated"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return True

def _is_authenticated(request: Request) -> bool:
    """Check if user is globally authenticated."""
    try:
        return bool(request.session.get("authenticated"))
    except Exception:
        return False

@app.get("/api/auth-status")
def get_auth_status(request: Request):
    """Return authentication status."""
    return {"authenticated": _is_authenticated(request)}

@app.post("/api/experiments/start")
def start_experiment(body: _StartExperimentBody, request: Request):
    # Require global admin authentication
    if not _is_authenticated(request):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    global _ACTIVE_EXPERIMENT
    # Allow dynamic addition of experiment folders without restart
    exp_path = os.path.join(_experiments_dir, body.name)
    if not os.path.isdir(exp_path):
        raise HTTPException(status_code=404, detail=f"Experiment '{body.name}' not found")
    if body.name not in _available_experiments:
        _available_experiments.append(body.name)
    # Lazy-mount experiment app if not already mounted
    if not _server_state.is_mounted(body.name):
        experiment_app = create_experiment_app(body.name)
        if experiment_app:
            app.mount(f"/exp/{body.name}", experiment_app)
            _server_state.add_mounted_experiment(body.name)
    active = _server_state.get_active_experiment()
    if active and active != body.name:
        raise HTTPException(status_code=409, detail=f"Experiment '{active}' is already active. Stop it first.")
    _server_state.set_active_experiment(body.name)
    return {"active": _server_state.get_active_experiment()}

@app.post("/api/experiments/stop")
def stop_experiment(request: Request):
    active = _server_state.get_active_experiment()
    if not active:
        raise HTTPException(status_code=400, detail="No active experiment to stop")
    # Require global admin authentication
    if not _is_authenticated(request):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    prev = active
    _server_state.set_active_experiment(None)
    # Clear authentication on stop
    try:
        request.session.clear()
    except Exception:
        pass
    return {"stopped": prev, "active": None}

experiments_dir = os.path.join(_project_root, "experiments")
if os.path.isdir(experiments_dir):
    for experiment_name in os.listdir(experiments_dir):
        if os.path.isdir(os.path.join(experiments_dir, experiment_name)):
            experiment_app = create_experiment_app(experiment_name)
            if experiment_app:
                app.mount(f"/exp/{experiment_name}", experiment_app)
                _server_state.add_mounted_experiment(experiment_name)

# -------------------------------
# Root-level Admin & Student APIs
# Bound to the default experiment context
# -------------------------------

class _RootLoginRequest(BaseModel):
    username: str
    password: str

@app.post("/admin/login")
async def root_login(request: Request, login_data: _RootLoginRequest):
    if login_data.username == _DEFAULT_ADMIN_USERNAME and _DEFAULT_ADMIN_VERIFY(login_data.password):
        request.session["authenticated"] = True
        return {"message": "Login successful"}
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

def _root_is_admin_authenticated(request: Request):
    # Global authentication check
    if request.session.get("authenticated"):
        return True
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

@app.post("/admin/logout")
async def root_logout(request: Request, response: Response):
    request.session.clear()
    response.delete_cookie("session")
    return {"message": "Logged out"}

@app.get("/admin/ping")
async def root_admin_ping(authenticated: bool = Depends(_root_is_admin_authenticated)):
    return {"ok": True}

def _require_active_root():
    if _server_state.get_active_experiment() is None:
        raise HTTPException(status_code=409, detail="No active experiment. Start one from the landing page.")
    return True

def _get_active_storage() -> Storage:
    """Return a Storage bound to the currently active experiment DB."""
    active = _server_state.get_active_experiment()
    if active is None:
        raise HTTPException(status_code=409, detail="No active experiment. Start one from the landing page.")
    db_path = os.path.join(_experiments_dir, active, "db", "students.db")
    return Storage(db_path)

def _get_active_registry() -> Dict[str, Callable[..., Any]]:
    """Return a function registry for the active experiment."""
    active = _server_state.get_active_experiment()
    if active is None:
        raise HTTPException(status_code=409, detail="No active experiment. Start one from the landing page.")
    funcs_dir = os.path.join(_experiments_dir, active, "funcs")
    return _load_functions_from_directory(funcs_dir)

# Combined dependency: require admin AND active experiment (root)
def _require_admin_and_active_root(
    authenticated: bool = Depends(_root_is_admin_authenticated),
    _active_ok: bool = Depends(_require_active_root),
):
    return True

@app.get("/functions", dependencies=[Depends(_require_active_root)])
def root_list_functions():
    registry = _get_active_registry()
    return {
        name: {
            "signature": str(inspect.signature(fn)),
            "doc": (fn.__doc__ or "").strip()
        }
        for name, fn in registry.items()
    }

# Students list requires admin + active experiment
@app.get("/students")
def root_list_students_admin(authenticated: bool = Depends(_root_is_admin_authenticated), _active_ok: bool = Depends(_require_active_root)):
    storage = _get_active_storage()
    return {"students": storage.list_students()}

class _RootCallRequest(BaseModel):
    student_id: str = Field(..., max_length=255)
    func_name: str = Field(..., max_length=255)
    args: list[Any] = []
    trial: Optional[str] = Field(None, max_length=255)
    experiment: Optional[str] = Field(None, max_length=255)
    experiment_name: str = Field(..., max_length=255)

    @validator('student_id', 'func_name', 'experiment_name')
    def validate_safe_strings(cls, v):
        return _validate_safe_string(v)
    
    @validator('trial', 'experiment')
    def validate_optional_strings(cls, v):
        if v is not None:
            return _validate_safe_string(v, allow_empty=True)
        return v
    
    @validator('args')
    def validate_args(cls, v):
        return _validate_function_args(v)

@app.post("/call", dependencies=[Depends(_require_active_root)])
def root_call_function(req: _RootCallRequest = Body(...)):
    storage = _get_active_storage()
    registry = _get_active_registry()
    # Require explicit experiment_name from client and verify it matches the active experiment
    active = _server_state.get_active_experiment()
    if req.experiment_name != active:
        raise HTTPException(status_code=409, detail=f"Mismatched experiment context. Active='{active}', got='{req.experiment_name}'.")
    if req.func_name not in registry:
        raise HTTPException(status_code=404, detail=f"Function '{req.func_name}' not found")
    if not storage.student_exists(req.student_id):
        raise HTTPException(status_code=403, detail=f"Invalid student ID '{req.student_id}'")
    fn = registry[req.func_name]
    trial_name = req.trial or req.experiment
    try:
        result = _invoke_and_log(
            storage=storage, fn=fn, func_name=req.func_name,
            args=req.args, student_id=req.student_id, trial=trial_name,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Function execution error: {e}")
    return {"result": jsonable_encoder(result)}

class _RootAddStudentBody(BaseModel):
    student_id: str
    name: str
    email: Optional[str] = None

@app.post("/admin/add-student", dependencies=[Depends(_require_admin_and_active_root)])
def root_add_student(body: _RootAddStudentBody = Body(...)):
    storage = _get_active_storage()
    storage.add_student(student_id=body.student_id, name=body.name, email=body.email)
    return {"status": "ok"}

@app.get("/admin/students", dependencies=[Depends(_require_admin_and_active_root)])
def root_list_all_students():
    storage = _get_active_storage()
    return {"students": storage.list_students()}

@app.delete("/admin/student/{student_id}", status_code=200, dependencies=[Depends(_require_admin_and_active_root)])
def root_remove_student(student_id: str):
    storage = _get_active_storage()
    was_deleted = storage.delete_student(student_id)
    if not was_deleted:
        raise HTTPException(status_code=404, detail=f"Student ID '{student_id}' not found.")
    return {"status": "ok", "message": f"Student '{student_id}' and all associated logs have been deleted."}

@app.get("/admin/logs", dependencies=[Depends(_require_admin_and_active_root)])
def root_get_server_logs(
    student_id: Optional[str] = Query(None),
    experiment_name: Optional[str] = Query(None),
    trial: Optional[str] = Query(None),
    n: int = Query(100, ge=1, le=10_000),
    order: Literal["latest", "earliest"] = Query("latest"),
):
    storage = _get_active_storage()
    eff_trial = trial or experiment_name
    logs = storage.fetch_logs(student_id=student_id, trial=eff_trial, n=n, order=order)
    return {"logs": logs}

@app.delete("/admin/logs/student/{student_id}", status_code=200, dependencies=[Depends(_require_admin_and_active_root)])
def root_delete_logs_for_student(student_id: str):
    storage = _get_active_storage()
    deleted = storage.delete_logs_by_student(student_id)
    return {"status": "ok", "deleted": deleted}

@app.get("/logs")
def root_get_logs(
    student_id: Optional[str] = Query(None),
    experiment_name: Optional[str] = Query(None),
    sid: Optional[str] = Query(None),
    exp: Optional[str] = Query(None),
    trial: Optional[str] = Query(None),
    trial_name: Optional[str] = Query(None),
    n: int = Query(100, ge=1, le=10_000),
    order: Literal["latest", "earliest"] = Query("latest"),
    start_time: Optional[datetime.datetime] = Query(None),
    end_time: Optional[datetime.datetime] = Query(None),
    _active_ok: bool = Depends(_require_active_root),
):
    storage = _get_active_storage()
    eff_student, eff_experiment = _resolve_log_filters(
        student_id=student_id, sid=sid,
        experiment_name=experiment_name, exp=exp,
        trial=trial, trial_name=trial_name,
    )
    logs = storage.fetch_logs(
        student_id=eff_student,
        trial=eff_experiment,
        n=n,
        order=order,
        start_time=start_time,
        end_time=end_time,
    )
    return {"logs": logs}

@app.get("/log-options")
def root_get_log_options():
    storage = _get_active_storage()
    students = storage.distinct_students_with_logs()
    experiments = storage.distinct_experiments()
    return {"students": students, "experiments": experiments, "trials": experiments}

@app.get("/is-registered", dependencies=[Depends(_require_active_root)])
def root_is_registered(student_id: str = Query(...)):
    storage = _get_active_storage()
    return {"registered": bool(storage.student_exists(student_id))}

@app.post("/admin/reload-functions", dependencies=[Depends(_require_admin_and_active_root)])
def root_reload_functions():
    """No-op for root; functions are loaded on demand from the active experiment."""
    registry = _get_active_registry()
    return {"status": "ok", "functions": len(registry)}
