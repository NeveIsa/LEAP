
# rpc_server.py
from fastapi import FastAPI, HTTPException, Query, Depends, status, Request, Response
from fastapi.staticfiles import StaticFiles
from starlette.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
from typing import Any, Callable, Dict, Optional, Literal
from starlette.middleware.sessions import SessionMiddleware
import secrets
import json
import os
import sys
import datetime

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from storage_orm import Storage
from .utils import (
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

# Use a single session secret across root and mounted experiment apps
SESSION_SECRET_KEY = os.environ.get("SESSION_SECRET_KEY", "super-secret-key-please-change-me-in-prod")
# Rotate runtime secret each start to invalidate old sessions
_STARTUP_NONCE = secrets.token_hex(16)
_DERIVED_SESSION_SECRET = f"{SESSION_SECRET_KEY}:{_STARTUP_NONCE}"
print("Session secret rotated at startup; previous sessions invalidated.")
SESSION_KW = dict(max_age=7*24*3600, same_site="lax", https_only=False, path="/")
_ACTIVE_EXPERIMENT: Optional[str] = None
_mounted_experiments: set[str] = set()

def _enc(obj: Any) -> str:
    """Best-effort JSON encoding for logging."""
    try:
        return json.dumps(jsonable_encoder(obj))
    except Exception:
        try:
            return json.dumps(repr(obj))
        except Exception:
            return 'null'

def _resolve_log_filters(
    *,
    student_id: Optional[str], sid: Optional[str],
    experiment_name: Optional[str], exp: Optional[str],
    trial: Optional[str], trial_name: Optional[str],
) -> tuple[Optional[str], Optional[str]]:
    """Resolve query params for logs into effective student and trial."""
    eff_student = student_id or sid
    eff_trial = trial or trial_name or experiment_name or exp
    return eff_student, eff_trial

def _invoke_and_log(
    *, storage: Storage, fn: Callable[..., Any], func_name: str,
    args: list[Any], student_id: str, trial: Optional[str],
):
    """Invoke function and persist result/error to storage."""
    try:
        result = fn(*args)
        storage.log_event(
            student_id=student_id,
            experiment_name=trial,
            func_name=func_name,
            args_json=_enc(args),
            result_json=_enc(result),
            error=None,
        )
        return result
    except Exception as e:
        storage.log_event(
            student_id=student_id,
            experiment_name=trial,
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
        print(f"Warning: Database file not found at {db_path}. A new one will be created.")
    funcs_dir = os.path.join(experiment_dir, "funcs")
    ui_dir = os.path.join(experiment_dir, "ui")
    admin_creds_path = os.path.join(experiment_dir, "admin_credentials.json")

    print(f"Creating app for experiment '{experiment_name}' with db_path: {db_path}")
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

    ADMIN_USERNAME, ADMIN_PASSWORD = _load_admin_credentials_from_path(admin_creds_path)

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
        global _ACTIVE_EXPERIMENT
        if _ACTIVE_EXPERIMENT is None:
            raise HTTPException(status_code=409, detail="No active experiment. Start it from the landing page.")
        if _ACTIVE_EXPERIMENT != experiment_name:
            raise HTTPException(status_code=409, detail=f"Experiment '{_ACTIVE_EXPERIMENT}' is active. Open that UI or stop it first.")
        return True

    # Combined dependency: require admin AND active experiment (per-experiment)
    def _require_admin_and_active(
        authenticated: bool = Depends(is_admin_authenticated),
        _active_ok: bool = Depends(_require_active_this_experiment),
    ):
        return True

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
        student_id: str
        func_name: str
        args: list[Any] = []
        # New preferred name for tagging runs; kept 'experiment' for backward compatibility
        trial: Optional[str] = None
        experiment: Optional[str] = None
        # Explicit experiment context; must match active experiment for root calls
        experiment_name: Optional[str] = None

    @app.post("/call")
    def call_function(req: CallRequest):
        # Enforce experiment context: only allow calls when THIS experiment is active
        global _ACTIVE_EXPERIMENT
        if _ACTIVE_EXPERIMENT is None:
            raise HTTPException(status_code=409, detail="No active experiment. Start one from the landing page.")
        if _ACTIVE_EXPERIMENT != experiment_name:
            raise HTTPException(status_code=409, detail=f"Experiment '{_ACTIVE_EXPERIMENT}' is active. Open that UI or stop it first.")
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
        n: int = Query(100, ge=1, le=1000),
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
        n: int = Query(100, ge=1, le=1000),
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
        current_active=lambda: _ACTIVE_EXPERIMENT,
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
    _default_admin_creds = os.path.join(_default_exp_dir, "admin_credentials.json")

    print(f"Root APIs bound to experiment '{_DEFAULT_EXPERIMENT}' with db at: {_default_db_path}")

    _default_storage = Storage(_default_db_path)
    _default_function_registry: Dict[str, Callable[..., Any]] = _load_functions_from_directory(_default_funcs_dir)
    _DEFAULT_ADMIN_USERNAME, _DEFAULT_ADMIN_PASSWORD = _load_admin_credentials_from_path(_default_admin_creds)
else:
    _default_ui_dir = os.path.join(_project_root, "experiments", "default", "ui")
    _default_storage = None
    _default_function_registry = {}
    _DEFAULT_ADMIN_USERNAME = _DEFAULT_ADMIN_PASSWORD = "admin"

# Mount default experiment UI at /ui and keep /static for compatibility
if os.path.isdir(_default_ui_dir):
    app.mount("/ui", StaticFiles(directory=_default_ui_dir), name="ui")
    app.mount("/static", StaticFiles(directory=_default_ui_dir), name="static")

@app.get("/")
async def read_index():
    return FileResponse(os.path.join(_current_dir, 'landing/index.html'))

@app.get("/api/experiments")
def list_experiments():
    experiments_dir = os.path.join(_project_root, "experiments")
    if not os.path.isdir(experiments_dir):
        return []
    return [d for d in os.listdir(experiments_dir) if os.path.isdir(os.path.join(experiments_dir, d))]

@app.get("/api/active-experiment")
def get_active_experiment():
    return {"active": _ACTIVE_EXPERIMENT}

@app.get("/api/health")
def health():
    return {"ok": True, "active": _ACTIVE_EXPERIMENT, "version": APP_VERSION}

class _StartExperimentBody(BaseModel):
    name: str

# Require root admin auth for starting/stopping experiments
def _require_root_admin_for_api(request: Request):
    if not request.session.get("authenticated"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return True

@app.post("/api/experiments/start")
def start_experiment(body: _StartExperimentBody, _auth_ok: bool = Depends(_require_root_admin_for_api)):
    global _ACTIVE_EXPERIMENT
    # Allow dynamic addition of experiment folders without restart
    exp_path = os.path.join(_experiments_dir, body.name)
    if not os.path.isdir(exp_path):
        raise HTTPException(status_code=404, detail=f"Experiment '{body.name}' not found")
    if body.name not in _available_experiments:
        _available_experiments.append(body.name)
    # Lazy-mount experiment app if not already mounted
    if body.name not in _mounted_experiments:
        experiment_app = create_experiment_app(body.name)
        if experiment_app:
            app.mount(f"/exp/{body.name}", experiment_app)
            _mounted_experiments.add(body.name)
    if _ACTIVE_EXPERIMENT and _ACTIVE_EXPERIMENT != body.name:
        raise HTTPException(status_code=409, detail=f"Experiment '{_ACTIVE_EXPERIMENT}' is already active. Stop it first.")
    _ACTIVE_EXPERIMENT = body.name
    return {"active": _ACTIVE_EXPERIMENT}

@app.post("/api/experiments/stop")
def stop_experiment(_auth_ok: bool = Depends(_require_root_admin_for_api)):
    global _ACTIVE_EXPERIMENT
    if not _ACTIVE_EXPERIMENT:
        raise HTTPException(status_code=400, detail="No active experiment to stop")
    prev = _ACTIVE_EXPERIMENT
    _ACTIVE_EXPERIMENT = None
    return {"stopped": prev, "active": None}

experiments_dir = os.path.join(_project_root, "experiments")
if os.path.isdir(experiments_dir):
    for experiment_name in os.listdir(experiments_dir):
        if os.path.isdir(os.path.join(experiments_dir, experiment_name)):
            experiment_app = create_experiment_app(experiment_name)
            if experiment_app:
                app.mount(f"/exp/{experiment_name}", experiment_app)
                _mounted_experiments.add(experiment_name)

# -------------------------------
# Root-level Admin & Student APIs
# Bound to the default experiment context
# -------------------------------

class _RootLoginRequest(BaseModel):
    username: str
    password: str

@app.post("/admin/login")
async def root_login(request: Request, login_data: _RootLoginRequest):
    if login_data.username == _DEFAULT_ADMIN_USERNAME and login_data.password == _DEFAULT_ADMIN_PASSWORD:
        request.session["authenticated"] = True
        return {"message": "Login successful"}
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

def _root_is_admin_authenticated(request: Request):
    if not request.session.get("authenticated"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return True

@app.post("/admin/logout")
async def root_logout(request: Request, response: Response):
    request.session.clear()
    response.delete_cookie("session")
    return {"message": "Logged out"}

@app.get("/admin/ping")
async def root_admin_ping(authenticated: bool = Depends(_root_is_admin_authenticated)):
    return {"ok": True}

def _require_active_root():
    global _ACTIVE_EXPERIMENT
    if _ACTIVE_EXPERIMENT is None:
        raise HTTPException(status_code=409, detail="No active experiment. Start one from the landing page.")
    return True

# Combined dependency: require admin AND active experiment (root)
def _require_admin_and_active_root(
    authenticated: bool = Depends(_root_is_admin_authenticated),
    _active_ok: bool = Depends(_require_active_root),
):
    return True

@app.get("/functions")
def root_list_functions():
    if _DEFAULT_EXPERIMENT is None:
        raise HTTPException(status_code=503, detail="No experiments available")
    return {
        name: {
            "signature": str(inspect.signature(fn)),
            "doc": (fn.__doc__ or "").strip()
        }
        for name, fn in _default_function_registry.items()
    }

# Students list requires admin + active experiment
@app.get("/students")
def root_list_students_admin(authenticated: bool = Depends(_root_is_admin_authenticated), _active_ok: bool = Depends(_require_active_root)):
    if _DEFAULT_EXPERIMENT is None or _default_storage is None:
        raise HTTPException(status_code=503, detail="No experiments available")
    return {"students": _default_storage.list_students()}

class _RootCallRequest(BaseModel):
    student_id: str
    func_name: str
    args: list[Any] = []
    trial: Optional[str] = None
    experiment: Optional[str] = None
    experiment_name: Optional[str] = None

@app.post("/call")
def root_call_function(req: _RootCallRequest):
    if _DEFAULT_EXPERIMENT is None:
        raise HTTPException(status_code=503, detail="No experiments available")
    if req.func_name not in _default_function_registry:
        raise HTTPException(status_code=404, detail=f"Function '{req.func_name}' not found")
    if not _default_storage or not _default_storage.student_exists(req.student_id):
        raise HTTPException(status_code=403, detail=f"Invalid student ID '{req.student_id}'")

    # Enforce experiment context against active experiment
    global _ACTIVE_EXPERIMENT
    ctx = req.experiment_name
    if _ACTIVE_EXPERIMENT is None:
        raise HTTPException(status_code=409, detail="No active experiment. Please start one from the landing page.")
    if not ctx:
        raise HTTPException(status_code=409, detail="Missing experiment_name in request.")
    if ctx != _ACTIVE_EXPERIMENT:
        raise HTTPException(status_code=409, detail=f"Mismatched experiment context. Active='{_ACTIVE_EXPERIMENT}', got='{ctx}'.")

    fn = _default_function_registry[req.func_name]
    trial_name = req.trial or req.experiment
    try:
        result = _invoke_and_log(
            storage=_default_storage, fn=fn, func_name=req.func_name,
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
def root_add_student(body: _RootAddStudentBody):
    if _DEFAULT_EXPERIMENT is None or _default_storage is None:
        raise HTTPException(status_code=503, detail="No experiments available")
    _default_storage.add_student(student_id=body.student_id, name=body.name, email=body.email)
    return {"status": "ok"}

@app.get("/admin/students", dependencies=[Depends(_require_admin_and_active_root)])
def root_list_all_students():
    if _DEFAULT_EXPERIMENT is None or _default_storage is None:
        raise HTTPException(status_code=503, detail="No experiments available")
    return {"students": _default_storage.list_students()}

@app.delete("/admin/student/{student_id}", status_code=200, dependencies=[Depends(_require_admin_and_active_root)])
def root_remove_student(student_id: str):
    if _DEFAULT_EXPERIMENT is None or _default_storage is None:
        raise HTTPException(status_code=503, detail="No experiments available")
    was_deleted = _default_storage.delete_student(student_id)
    if not was_deleted:
        raise HTTPException(status_code=404, detail=f"Student ID '{student_id}' not found.")
    return {"status": "ok", "message": f"Student '{student_id}' and all associated logs have been deleted."}

@app.get("/admin/logs", dependencies=[Depends(_require_admin_and_active_root)])
def root_get_server_logs(
    student_id: Optional[str] = Query(None),
    experiment_name: Optional[str] = Query(None),
    trial: Optional[str] = Query(None),
    n: int = Query(100, ge=1, le=1000),
    order: Literal["latest", "earliest"] = Query("latest"),
):
    if _DEFAULT_EXPERIMENT is None or _default_storage is None:
        raise HTTPException(status_code=503, detail="No experiments available")
    eff_trial = trial or experiment_name
    logs = _default_storage.fetch_logs(student_id=student_id, experiment_name=eff_trial, n=n, order=order)
    return {"logs": logs}

@app.get("/logs")
def root_get_logs(
    student_id: Optional[str] = Query(None),
    experiment_name: Optional[str] = Query(None),
    sid: Optional[str] = Query(None),
    exp: Optional[str] = Query(None),
    trial: Optional[str] = Query(None),
    trial_name: Optional[str] = Query(None),
    n: int = Query(100, ge=1, le=1000),
    order: Literal["latest", "earliest"] = Query("latest"),
    start_time: Optional[datetime.datetime] = Query(None),
    end_time: Optional[datetime.datetime] = Query(None),
    _active_ok: bool = Depends(_require_active_root),
):
    if _DEFAULT_EXPERIMENT is None or _default_storage is None:
        raise HTTPException(status_code=503, detail="No experiments available")
    eff_student, eff_experiment = _resolve_log_filters(
        student_id=student_id, sid=sid,
        experiment_name=experiment_name, exp=exp,
        trial=trial, trial_name=trial_name,
    )
    logs = _default_storage.fetch_logs(
        student_id=eff_student,
        experiment_name=eff_experiment,
        n=n,
        order=order,
        start_time=start_time,
        end_time=end_time,
    )
    return {"logs": logs}

@app.get("/log-options")
def root_get_log_options():
    if _DEFAULT_EXPERIMENT is None or _default_storage is None:
        raise HTTPException(status_code=503, detail="No experiments available")
    students = _default_storage.distinct_students_with_logs()
    experiments = _default_storage.distinct_experiments()
    return {"students": students, "experiments": experiments, "trials": experiments}

@app.get("/is-registered")
def root_is_registered(student_id: str = Query(...)):
    if _DEFAULT_EXPERIMENT is None or _default_storage is None:
        raise HTTPException(status_code=503, detail="No experiments available")
    return {"registered": bool(_default_storage.student_exists(student_id))}

@app.post("/admin/reload-functions")
def root_reload_functions(authenticated: bool = Depends(_root_is_admin_authenticated)):
    if _DEFAULT_EXPERIMENT is None:
        raise HTTPException(status_code=503, detail="No experiments available")
    # Refresh in place to avoid rebinding the global variable
    _default_function_registry.clear()
    _default_function_registry.update(_load_functions_from_directory(_default_funcs_dir))
    return {"status": "ok", "functions": len(_default_function_registry)}
