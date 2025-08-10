# rpc_server.py
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
from typing import Any, Callable, Dict, Optional, Literal
import importlib
import inspect
import json
import os

# Swap in ORM-based storage (SQLAlchemy + duckdb-engine)
import storage_orm as storage

FUNCTIONS_MODULE = os.environ.get("RPC_FUNCTIONS_MODULE", "functions")
storage.init_db()

FUNCTION_REGISTRY: Dict[str, Callable[..., Any]] = {}

def load_functions(module_name: str = FUNCTIONS_MODULE) -> Dict[str, Callable[..., Any]]:
    try:
        mod = importlib.import_module(module_name)
        mod = importlib.reload(mod)
    except Exception as e:
        raise RuntimeError(f"Failed to import module '{module_name}': {e}")
    funcs = {}
    for name, obj in vars(mod).items():
        if name.startswith("_"):
            continue
        if inspect.isfunction(obj):
            funcs[name] = obj
    if not funcs:
        raise RuntimeError(f"No public functions found in module '{module_name}'.")
    return funcs

def register_all_functions():
    global FUNCTION_REGISTRY
    FUNCTION_REGISTRY = load_functions(FUNCTIONS_MODULE)

register_all_functions()

class CallRequest(BaseModel):
    student_id: str
    func_name: str
    args: list[Any] = []

app = FastAPI(title="Classroom RPC Server", version="0.4.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*", "null"],  # Allows all origins, including file://
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

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
        raise HTTPException(status_code=403, detail="Invalid student ID")

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
            func_name=req.func_name,
            args_json=_enc(req.args),
            result_json=_enc(result),
            error=None,
        )
    except Exception as e:
        storage.log_event(
            student_id=req.student_id,
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
def add_student(body: AddStudentBody):
    storage.add_student(student_id=body.student_id, name=body.name, email=body.email)
    return {"status": "ok"}

@app.get("/admin/students")
def list_all_students():
    """Returns a list of all registered student IDs."""
    return {"students": storage.list_students()}

@app.get("/admin/logs")
def get_server_logs(
    n: int = Query(100, ge=1, le=1000, description="Number of logs to retrieve"),
    student_id: Optional[str] = Query(None, description="Optional: Filter logs by student ID."),
    order: Literal["latest", "earliest"] = Query("latest", description="Sort order: 'latest' or 'earliest'")
):
    """Returns the last N log events from the server, with optional filtering and ordering."""
    db_order = "desc" if order == "latest" else "asc"
    if student_id:
        if not storage.student_exists(student_id):
            raise HTTPException(status_code=404, detail=f"Student ID '{student_id}' not found.")
        logs = storage.fetch_logs_for_student(student_id=student_id, limit=n, order=db_order)
    else:
        logs = storage.fetch_logs(limit=n, order=db_order)
    return {"logs": logs}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("rpc_server:app", host="0.0.0.0", port=9000, reload=False)
