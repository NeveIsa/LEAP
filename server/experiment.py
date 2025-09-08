# experiment.py  
"""Experiment management and per-experiment app factory."""

import os
import inspect
from typing import Any, Callable, Dict
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from .storage_orm import Storage
from .utils import build_experiment_app

def create_experiment_app(experiment_name: str, project_root: str, session_secret: str, 
                         session_cookie_opts: dict, current_active: callable, 
                         invoke_and_log: callable) -> FastAPI:
    """Create a FastAPI app for a specific experiment."""
    return build_experiment_app(
        experiment_name=experiment_name,
        project_root=project_root,
        session_secret=session_secret,
        session_cookie_opts=session_cookie_opts,
        current_active=current_active,
        invoke_and_log=invoke_and_log,
    )

def get_active_storage(experiments_dir: str, active_experiment_getter) -> Storage:
    """Return a Storage bound to the currently active experiment DB."""
    active = active_experiment_getter()
    if active is None:
        raise HTTPException(status_code=409, detail="No active experiment. Start one from the landing page.")
    db_path = os.path.join(experiments_dir, active, "db", "students.db")
    return Storage(db_path)

def get_active_registry(experiments_dir: str, active_experiment_getter, load_functions_fn) -> Dict[str, Callable[..., Any]]:
    """Return a function registry for the active experiment."""
    active = active_experiment_getter()
    if active is None:
        raise HTTPException(status_code=409, detail="No active experiment. Start one from the landing page.")
    funcs_dir = os.path.join(experiments_dir, active, "funcs")
    return load_functions_fn(funcs_dir)

def require_active_experiment(active_experiment_getter):
    """Dependency to ensure an experiment is active."""
    if active_experiment_getter() is None:
        raise HTTPException(status_code=409, detail="No active experiment. Start one from the landing page.")
    return True