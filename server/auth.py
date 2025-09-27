# auth.py
"""Authentication utilities and middleware."""

import os
from fastapi import HTTPException, Request, status
from .utils import load_admin_credentials

# Load admin credentials
def load_default_admin_credentials():
    """Load default admin credentials."""
    try:
        # Use global admin credentials
        return load_admin_credentials()
    except Exception:
        # Fallback to default weak credentials
        print("🔓 Using default development credentials (admin/password) - change for production!")
        from .utils import make_password_hash, _build_verifier_from_record
        rec = make_password_hash("password")
        return "admin", _build_verifier_from_record(rec)

def is_authenticated(request: Request) -> bool:
    """Check if the request is globally authenticated."""
    try:
        return bool(request.session.get("authenticated"))
    except Exception:
        return False

def root_is_admin_authenticated(request: Request):
    """Root authentication check."""
    # Global authentication check
    if request.session.get("authenticated"):
        return True
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")