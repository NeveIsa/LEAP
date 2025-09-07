from __future__ import annotations

import glob
import importlib.util
import inspect
import json
import os
from typing import Any, Callable, Dict, Optional

from fastapi.encoders import jsonable_encoder
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware
from fastapi import FastAPI, HTTPException, Depends, status, Query, Request, Response
from fastapi.staticfiles import StaticFiles
from typing import Literal, Any, Optional, Dict
from pydantic import BaseModel
import datetime
from .storage_orm import Storage


def enc(obj: Any) -> str:
    """Best-effort JSON encoding for logging."""
    try:
        return json.dumps(jsonable_encoder(obj))
    except Exception:
        try:
            return json.dumps(repr(obj))
        except Exception:
            return 'null'


def resolve_log_filters(
    *,
    student_id: Optional[str], sid: Optional[str],
    experiment_name: Optional[str], exp: Optional[str],
    trial: Optional[str], trial_name: Optional[str],
) -> tuple[Optional[str], Optional[str]]:
    """Resolve query params for logs into effective student and trial."""
    eff_student = student_id or sid
    eff_trial = trial or trial_name or experiment_name or exp
    return eff_student, eff_trial


def load_functions_from_directory(directory: str) -> Dict[str, Callable[..., Any]]:
    funcs: Dict[str, Callable[..., Any]] = {}
    for filepath in glob.glob(os.path.join(directory, "*.py")):
        module_name = os.path.splitext(os.path.basename(filepath))[0]
        spec = importlib.util.spec_from_file_location(f"funcs.{module_name}", filepath)
        if spec and spec.loader:
            try:
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
            except Exception as e:
                print(f"Error loading module '{module_name}' from '{filepath}': {e}")
                continue
            for name, obj in vars(mod).items():
                if name.startswith("_"):
                    continue
                if inspect.isfunction(obj):
                    if name in funcs:
                        print(f"Warning: Function '{name}' is being redefined in directory '{directory}'.")
                    funcs[name] = obj
    if not funcs:
        print(f"Warning: No public functions found in directory '{directory}'.")
    return funcs


def load_admin_credentials(admin_creds_path: str) -> tuple[str, str]:
    env_user = os.environ.get("ADMIN_USERNAME")
    env_pass = os.environ.get("ADMIN_PASSWORD")
    if env_user and env_pass:
        return env_user, env_pass
    try:
        if os.path.isfile(admin_creds_path):
            with open(admin_creds_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                username = data.get("username") or data.get("user")
                password = data.get("password") or data.get("pass")
                if username and password:
                    return username, password
    except Exception:
        pass
    return ("admin", "password")


class NoCacheHTMLMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        ct = response.headers.get('content-type', '')
        path = request.url.path
        if 'text/html' in ct and (path.startswith('/ui') or path.startswith('/exp/') or path == '/'):
            response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
        return response


def build_experiment_app(
    *,
    experiment_name: str,
    project_root: str,
    session_secret: str,
    session_cookie_opts: dict,
    current_active: callable,
    invoke_and_log: callable,
) -> FastAPI:
    """Factory to build a per‑experiment FastAPI app with identical behavior.

    Parameters mirror the current server wiring; behavior is unchanged.
    """
    experiment_dir = os.path.join(project_root, "experiments", experiment_name)
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
    function_registry = load_functions_from_directory(funcs_dir)

    app = FastAPI(title=f"Experiment: {experiment_name}")
    app.mount("/ui", StaticFiles(directory=ui_dir), name="ui")
    app.add_middleware(NoCacheHTMLMiddleware)
    app.add_middleware(SessionMiddleware, secret_key=session_secret, **session_cookie_opts)

    ADMIN_USERNAME, ADMIN_PASSWORD = load_admin_credentials(admin_creds_path)

    @app.post("/admin/login")
    async def login(request: Request):
        """Accept JSON or form body with username/password."""
        username = password = None
        try:
            data = await request.json()
            if isinstance(data, dict):
                username = data.get("username")
                password = data.get("password")
        except Exception:
            try:
                form = await request.form()
                username = form.get("username")
                password = form.get("password")
            except Exception:
                pass
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
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
        active = current_active()
        if active is None:
            raise HTTPException(status_code=409, detail="No active experiment. Start it from the landing page.")
        if active != experiment_name:
            raise HTTPException(status_code=409, detail=f"Experiment '{active}' is active. Open that UI or stop it first.")
        return True

    @app.post("/admin/reload-functions", dependencies=[Depends(is_admin_authenticated), Depends(_require_active_this_experiment)])
    def admin_reload_functions():
        nonlocal function_registry
        function_registry = load_functions_from_directory(funcs_dir)
        return {"status": "ok", "functions": len(function_registry)}

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
        trial: Optional[str] = None
        experiment: Optional[str] = None
        experiment_name: Optional[str] = None

    @app.post("/call")
    def call_function(req: CallRequest):
        # Enforce experiment context: only allow calls when THIS experiment is active
        active = current_active()
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
            result = invoke_and_log(
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

    @app.get("/logs", dependencies=[Depends(_require_active_this_experiment)])
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
    ):
        eff_student, eff_experiment = resolve_log_filters(
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

    return app
