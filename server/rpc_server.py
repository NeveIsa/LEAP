# rpc_server.py
from fastapi import FastAPI, HTTPException
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
from typing import Any, Callable, Dict
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

@app.post("/admin/add-student")
def add_student(body: AddStudentBody):
    storage.add_student(body.student_id)
    return {"status": "ok"}

@app.get("/admin/students")
def list_all_students():
    """Returns a list of all registered student IDs."""
    return {"students": storage.list_students()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("rpc_server:app", host="0.0.0.0", port=9000, reload=False)