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
import json

import logging

# Configure logging to a file
logging.basicConfig(filename='sql_debug.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logging.info("Logging configured and storage_orm.py imported.")

from sqlalchemy import create_engine, String, Integer, DateTime, Text, select, Sequence, asc, desc, delete, and_, distinct
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

def fetch_logs(
    *,
    student_id: Optional[str] = None,
    experiment_name: Optional[str] = None,
    n: int = 100,
    order: str = "latest",
    start_time: Optional[datetime.datetime] = None,
    end_time: Optional[datetime.datetime] = None,
) -> List[Dict[str, Any]]:
    """Fetch logs with optional filtering, ordering, and limit.

    Args:
        student_id: optional filter by student.
        experiment_name: optional filter by experiment.
        n: number of rows to return (default 100).
        order: 'latest' (desc) or 'earliest' (asc) by timestamp.
        start_time: optional filter for logs after this time.
        end_time: optional filter for logs before this time.
    """
    with SessionLocal() as s:
        stmt = select(Log)

        conditions = []
        if student_id:
            conditions.append(Log.student_id == student_id)
        if experiment_name:
            conditions.append(Log.experiment_name == experiment_name)
        if start_time:
            conditions.append(Log.ts >= start_time)
        if end_time:
            conditions.append(Log.ts <= end_time)

        if conditions:
            stmt = stmt.where(and_(*conditions))

        stmt = stmt.order_by(desc(Log.ts) if order != "earliest" else asc(Log.ts)).limit(int(max(1, min(n, 1000))))

        # Log the compiled SQL for debugging
        try:
            compiled_stmt = stmt.compile(dialect=sqlite.dialect(), compile_kwargs={"literal_binds": True})
            logging.info(f"Generated SQL statement: {compiled_stmt}")
        except Exception:
            pass

        rows = s.execute(stmt).scalars().all()

        def _iso_ts(dt: datetime.datetime) -> str:
            # Ensure timezone-aware ISO; assume stored UTC when naive
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=datetime.timezone.utc)
            return dt.isoformat()

        def _try_parse_json(json_str: Optional[str]) -> Any:
            if json_str is None:
                return None
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                return json_str

        return [
            {
                "ts": _iso_ts(r.ts),
                "student_id": r.student_id,
                "experiment_name": r.experiment_name,
                "func_name": r.func_name,
                "args_json": _try_parse_json(r.args_json),
                "result_json": _try_parse_json(r.result_json),
                "error": r.error,
            }
            for r in rows
        ]

def distinct_students_with_logs() -> List[str]:
    """Return distinct student_ids that have at least one log, sorted."""
    with SessionLocal() as s:
        rows = s.execute(select(distinct(Log.student_id)).order_by(asc(Log.student_id))).all()
        return [r[0] for r in rows if r and r[0]]

def distinct_experiments() -> List[str]:
    """Return distinct non-null experiment_name values from logs, sorted."""
    with SessionLocal() as s:
        rows = s.execute(select(distinct(Log.experiment_name)).where(Log.experiment_name.is_not(None)).order_by(asc(Log.experiment_name))).all()
        return [r[0] for r in rows if r and r[0]]

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
