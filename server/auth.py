# auth.py
"""Authentication utilities and middleware."""

import os
from fastapi import HTTPException, Request, status
from .utils import load_admin_credentials

# Load admin credentials
def load_default_admin_credentials():
    """Load default admin credentials."""
    try:
        admin_creds_path = os.path.join(os.path.dirname(__file__), "..", "admin_credentials.json")
        return load_admin_credentials(admin_creds_path)
    except Exception:
        # Fallback to default weak credentials
        print("🔓 Using default development credentials (admin/password) - change for production!")
        from .utils import make_password_hash, _build_verifier_from_record
        rec = make_password_hash("password")
        return "admin", _build_verifier_from_record(rec)

def is_authed_for_experiment(request: Request, experiment_name: str) -> bool:
    """Check if the request is authenticated for a specific experiment."""
    try:
        auth_experiments = request.session.get("auth_experiments") or {}
        return auth_experiments.get(experiment_name, False)
    except Exception:
        return False

def root_is_admin_authenticated(request: Request, active_experiment_getter):
    """Root authentication check with fallback to active experiment auth."""
    # Root auth via global flag or scoped experiment auth for the active experiment
    if request.session.get("authenticated"):
        return True
    try:
        active = active_experiment_getter()
        if active and is_authed_for_experiment(request, active):
            return True
    except Exception:
        pass
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")