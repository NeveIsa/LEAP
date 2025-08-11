# storage_orm.py
"""
DuckDB storage layer using SQLAlchemy 2.0 ORM (object-resource model).
Requires: sqlalchemy>=2, duckdb, duckdb-engine
    pip install "SQLAlchemy>=2" duckdb duckdb-engine
"""

from __future__ import annotations
from typing import Optional, List, Dict, Any
import os
import datetime

import logging

# Configure logging to a file
logging.basicConfig(filename='sql_debug.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logging.info("Logging configured and storage_orm.py imported.")

from sqlalchemy import create_engine, String, Integer, DateTime, Text, select, Sequence, asc, desc, delete, and_
from sqlalchemy.dialects import sqlite
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

# ---------------------------------------------------------------------
# Engine & Session
# ---------------------------------------------------------------------
_current_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_current_dir)
DB_FILE = os.environ.get("RPC_DB_FILE", os.path.join(_project_root, "db/students.db"))
engine = create_engine(f"duckdb:///{DB_FILE}", future=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, future=True)

# ---------------------------------------------------------------------
# ORM Models
# ---------------------------------------------------------------------
class Base(DeclarativeBase):
    pass

class Student(Base):
    __tablename__ = "students"
    student_id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    email: Mapped[Optional[str]] = mapped_column(String, nullable=True)

log_id_seq = Sequence('log_id_seq')

class Log(Base):
    __tablename__ = "logs"
    id: Mapped[int] = mapped_column(Integer, log_id_seq, primary_key=True, server_default=log_id_seq.next_value())
    ts: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow, index=True, nullable=False)
    student_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    experiment_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    func_name: Mapped[str] = mapped_column(String, index=True, nullable=False)
    args_json: Mapped[str] = mapped_column(Text, nullable=False)
    result_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

# ---------------------------------------------------------------------
# API
# ---------------------------------------------------------------------
def init_db() -> None:
    """Create tables if missing and apply basic migrations."""
    Base.metadata.create_all(engine)
    # Basic migration: add experiment_name to logs if missing
    try:
        with engine.connect() as conn:
            cols = conn.exec_driver_sql("PRAGMA table_info('logs')").fetchall()
            names = {row[1] for row in cols} if cols else set()
            if 'experiment_name' not in names:
                conn.exec_driver_sql("ALTER TABLE logs ADD COLUMN experiment_name VARCHAR NULL")
    except Exception:
        # Best-effort migration; ignore if PRAGMA not supported or other errors
        pass

def add_student(student_id: str, name: str, email: Optional[str] = None) -> None:
    """Idempotent insert of a student."""
    with SessionLocal() as s:
        if not s.get(Student, student_id):
            s.add(Student(student_id=student_id, name=name, email=email))
            s.commit()

def student_exists(student_id: str) -> bool:
    with SessionLocal() as s:
        return s.get(Student, student_id) is not None


def list_students() -> List[Dict[str, Any]]:
    """Returns a list of all registered students."""
    with SessionLocal() as s:
        students = s.execute(select(Student).order_by(Student.student_id)).scalars().all()
        return [
            {"student_id": s.student_id, "name": s.name, "email": s.email}
            for s in students
        ]

def delete_student(student_id: str) -> bool:
    """Deletes a student and all their associated logs. Returns True if deleted, False otherwise."""
    with SessionLocal() as s:
        student = s.get(Student, student_id)
        if student:
            # Delete logs first
            s.execute(delete(Log).where(Log.student_id == student_id))
            # Then delete the student
            s.delete(student)
            s.commit()
            return True
        return False


def log_event(*, student_id: str, experiment_name: Optional[str], func_name: str, args_json: str, result_json: Optional[str], error: Optional[str]) -> None:
    with SessionLocal() as s:
        s.add(Log(student_id=student_id, experiment_name=experiment_name, func_name=func_name, args_json=args_json, result_json=result_json, error=error))
        try:
            s.commit()
        except Exception as e:
            # If the DB is missing the experiment_name column (older schema), try to migrate on the fly once
            msg = str(e).lower()
            s.rollback()
            if "experiment_name" in msg and "does not have a column" in msg:
                try:
                    init_db()
                    s.add(Log(student_id=student_id, experiment_name=experiment_name, func_name=func_name, args_json=args_json, result_json=result_json, error=error))
                    s.commit()
                    return
                except Exception:
                    s.rollback()
            # Re-raise original error if migration or retry didn't work
            raise

def fetch_logs(student_id: Optional[str] = None, experiment_name: Optional[str] = None) -> List[Dict[str, Any]]:
    """Fetches logs, allowing for filtering."""
    with SessionLocal() as s:
        stmt = select(Log)
        
        conditions = []
        if student_id:
            conditions.append(Log.student_id == student_id)
        if experiment_name:
            conditions.append(Log.experiment_name == experiment_name)
        
        if conditions:
            stmt = stmt.where(and_(*conditions))
        
        # Compile the statement to get the raw SQL string
        compiled_stmt = stmt.compile(dialect=sqlite.dialect(), compile_kwargs={"literal_binds": True})
        logging.info(f"Generated SQL statement: {compiled_stmt}")
        
        rows = s.execute(stmt).scalars().all() # Removed order_by and limit
        return [
            {
                "ts": r.ts.isoformat(),
                "student_id": r.student_id,
                "experiment_name": r.experiment_name,
                "func_name": r.func_name,
                "args_json": r.args_json,
                "result_json": r.result_json,
                "error": r.error,
            }
            for r in rows
        ]

if __name__ == "__main__":
    # Example usage
    print("Initializing DB...")
    init_db()
    print("Adding student 's001'...")
    add_student("s001", name="Alice", email="alice@example.com")
    print("Adding student 's002'...")
    add_student("s002", name="Bob")
    print("Logging some events...")
    log_event(student_id="s001", func_name="square", args_json='[2]', result_json='4', error=None)
    log_event(student_id="s002", func_name="rosenbrock", args_json='[1, 2, 1, 100]', result_json='100', error=None)
    log_event(student_id="s001", func_name="cubic", args_json='[3]', result_json='27', error=None)
    log_event(student_id="s001", func_name="cubic", args_json='["a"]', result_json=None, error="TypeError: unsupported operand type(s) for *: 'str' and 'str'")
    print("\nFetching all logs:")
    for log in fetch_logs():
        print(log)
    print("\nFetching logs for s001:")
    for log in fetch_logs_for_student("s001"):
        print(log)
