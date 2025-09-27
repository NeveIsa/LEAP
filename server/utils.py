from __future__ import annotations

import glob
import importlib.util
import inspect
import json
import os
from typing import Any, Callable, Dict, Optional
import re

from fastapi.encoders import jsonable_encoder
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware
from fastapi import FastAPI, HTTPException, Depends, status, Query, Request, Response
import logging
from fastapi.staticfiles import StaticFiles
from typing import Literal, Any, Optional, Dict
from pydantic import BaseModel
import datetime
try:
    from .storage_orm import Storage  # when imported as package (server.utils)
except ImportError:  # pragma: no cover
    from storage_orm import Storage  # when imported as script (utils)
import hashlib
import hmac
import os


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


def _pbkdf2(password: str, salt: bytes, iterations: int = 240_000, algo: str = "sha256") -> bytes:
    return hashlib.pbkdf2_hmac(algo, password.encode("utf-8"), salt, iterations)

def make_password_hash(password: str, *, iterations: int = 240_000, algo: str = "sha256", salt: Optional[bytes] = None) -> Dict[str, Any]:
    salt = salt or os.urandom(16)
    dk = _pbkdf2(password, salt, iterations, algo)
    return {
        "algorithm": f"pbkdf2_{algo}",
        "iterations": iterations,
        "salt": salt.hex(),
        "password_hash": dk.hex(),
    }

def _build_verifier_from_record(record: Dict[str, Any]):
    algo = record.get("algorithm", "pbkdf2_sha256")
    if not algo.startswith("pbkdf2_"):
        # default
        algo_name = "sha256"
    else:
        _, algo_name = algo.split("_", 1)
    try:
        iterations = int(record.get("iterations", 240_000))
    except Exception:
        iterations = 240_000
    try:
        salt = bytes.fromhex(record["salt"]) if isinstance(record.get("salt"), str) else b""
        pwd_hash = bytes.fromhex(record["password_hash"]) if isinstance(record.get("password_hash"), str) else b""
    except Exception:
        salt, pwd_hash = b"", b""

    def verify(pw: str) -> bool:
        if not salt or not pwd_hash:
            return False
        dk = _pbkdf2(pw, salt, iterations, algo_name)
        return hmac.compare_digest(dk, pwd_hash)

    return verify

def load_admin_credentials(admin_creds_path: str = None) -> tuple[str, callable]:
    """Return (username, verify_fn) for admin auth.
    
    Automatically migrates plaintext passwords to hashed format when detected.

    - Supports env ADMIN_USERNAME/ADMIN_PASSWORD (hashed in-memory)
    - JSON file supports:
        {"username": "...", "password_hash": "...", "salt": "...", "iterations": 240000, "algorithm": "pbkdf2_sha256"}
      Legacy plaintext {"username": "...", "password": "..."} is automatically migrated to hashed format.
    - If admin_creds_path is None, looks for global admin_credentials.json in project root
    """
    env_user = os.environ.get("ADMIN_USERNAME")
    env_pass = os.environ.get("ADMIN_PASSWORD")
    if env_user and env_pass:
        rec = make_password_hash(env_pass)
        return env_user, _build_verifier_from_record(rec)
    
    # If no path provided, use global admin credentials
    if admin_creds_path is None:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(current_dir)
        admin_creds_path = os.path.join(project_root, "admin_credentials.json")

    try:
        if os.path.isfile(admin_creds_path):
            with open(admin_creds_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                username = data.get("username") or data.get("user") or "admin"
                
                # Check if already hashed
                if data.get("password_hash") and data.get("salt"):
                    return username, _build_verifier_from_record(data)
                
                # Auto-migrate plaintext password to hashed format
                password = data.get("password") or data.get("pass")
                if password:
                    print(f"🔐 Migrating plaintext password to hashed format for: {admin_creds_path}")
                    rec = make_password_hash(password)
                    
                    # Create new hashed credentials
                    hashed_data = {
                        "username": username,
                        "algorithm": rec["algorithm"],
                        "iterations": rec["iterations"],
                        "salt": rec["salt"],
                        "password_hash": rec["password_hash"]
                    }
                    
                    # Write back to file securely
                    try:
                        with open(admin_creds_path, "w", encoding="utf-8") as f:
                            json.dump(hashed_data, f, indent=2)
                        print(f"✅ Password migration completed for: {admin_creds_path}")
                    except Exception as e:
                        print(f"⚠️  Could not write hashed credentials to {admin_creds_path}: {e}")
                        print("   Continuing with in-memory hash (password will need migration again next time)")
                    
                    return username, _build_verifier_from_record(rec)
                
                return username, (lambda _pw: False)
    except Exception as e:
        print(f"⚠️  Error loading credentials from {admin_creds_path}: {e}")
        pass
    
    # Default dev creds (weak) — recommend overriding in production
    print("🔓 Using default development credentials (admin/password) - change for production!")
    rec = make_password_hash("password")
    return "admin", _build_verifier_from_record(rec)


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

class ActiveExperimentUIGuard(BaseHTTPMiddleware):
    def __init__(self, app, *, experiment_name: str, current_active: callable):
        super().__init__(app)
        self.experiment_name = experiment_name
        self.current_active = current_active

    async def dispatch(self, request, call_next):
        try:
            path = request.url.path or ''
            active = self.current_active()
            # The middleware sees full paths like /exp/<experiment>/admin/login, not relative paths
            is_admin_path = f'/exp/{self.experiment_name}/admin' in path
            
            # Block all access when experiment is not active, except admin endpoints for authentication
            if not is_admin_path:
                logging.debug(f"ActiveExperimentUIGuard: path={path}, experiment={self.experiment_name}, active={active}")
                if active != self.experiment_name:
                    logging.info(f"Blocking access to {self.experiment_name} - not active (active: {active})")
                    from starlette.responses import RedirectResponse
                    return RedirectResponse(url='/', status_code=307)
        except Exception as e:
            logging.warning(f"ActiveExperimentUIGuard exception for {self.experiment_name}: {e}")
        return await call_next(request)


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
        logging.info("Database file not found at %s. A new one will be created.", db_path)
    funcs_dir = os.path.join(experiment_dir, "funcs")
    ui_dir = os.path.join(experiment_dir, "ui")
    # No longer using per-experiment credentials

    logging.debug("Creating app for experiment '%s' with db_path: %s", experiment_name, db_path)
    storage = Storage(db_path)
    function_registry = load_functions_from_directory(funcs_dir)

    app = FastAPI(title=f"Experiment: {experiment_name}")
    app.mount("/ui", StaticFiles(directory=ui_dir), name="ui")
    app.add_middleware(NoCacheHTMLMiddleware)
    app.add_middleware(ActiveExperimentUIGuard, experiment_name=experiment_name, current_active=current_active)
    app.add_middleware(SessionMiddleware, secret_key=session_secret, **session_cookie_opts)

    # Use global admin credentials for all experiments
    # Session cookie is shared (path=/), so logging in here authenticates root admin APIs.
    ADMIN_USERNAME, ADMIN_VERIFY = load_admin_credentials()

    @app.post("/admin/login")
    async def login(request: Request):
        """Per-experiment admin login (JSON or form)."""
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
        if username == ADMIN_USERNAME and ADMIN_VERIFY(password or ""):
            # Set global authentication flag instead of per-experiment
            request.session["authenticated"] = True
            return {"message": "Login successful"}
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    @app.post("/admin/logout")
    async def logout(request: Request, response: Response):
        # Clear global authentication
        request.session.clear()
        return {"message": "Logged out"}

    @app.get("/admin/ping")
    async def admin_ping(request: Request):
        if request.session.get("authenticated"):
            return {"ok": True}
        # Not authenticated
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

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

    # Note: other per-experiment APIs are intentionally omitted to avoid tight coupling.
    # All client/admin operations (students/logs/call) are provided at root and scoped to the active experiment.
    return app
