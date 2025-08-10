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

from sqlalchemy import create_engine, String, Integer, DateTime, Text, select, Sequence
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

# ---------------------------------------------------------------------
# Engine & Session
# ---------------------------------------------------------------------
DB_FILE = os.environ.get("RPC_DB_FILE", "students.db")
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

log_id_seq = Sequence('log_id_seq')

class Log(Base):
    __tablename__ = "logs"
    id: Mapped[int] = mapped_column(Integer, log_id_seq, primary_key=True, server_default=log_id_seq.next_value())
    ts: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow, index=True, nullable=False)
    student_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    func_name: Mapped[str] = mapped_column(String, index=True, nullable=False)
    args_json: Mapped[str] = mapped_column(Text, nullable=False)
    result_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

# ---------------------------------------------------------------------
# API
# ---------------------------------------------------------------------
def init_db() -> None:
    """Create tables if missing."""
    Base.metadata.create_all(engine)

def add_student(student_id: str) -> None:
    """Idempotent insert of a student."""
    with SessionLocal() as s:
        if not s.get(Student, student_id):
            s.add(Student(student_id=student_id))
            s.commit()

def student_exists(student_id: str) -> bool:
    with SessionLocal() as s:
        return s.get(Student, student_id) is not None

def log_event(*, student_id: str, func_name: str, args_json: str, result_json: Optional[str], error: Optional[str]) -> None:
    with SessionLocal() as s:
        s.add(Log(student_id=student_id, func_name=func_name, args_json=args_json, result_json=result_json, error=error))
        s.commit()

def fetch_logs(limit: int = 100) -> List[Dict[str, Any]]:
    with SessionLocal() as s:
        rows = s.execute(select(Log).order_by(Log.ts.desc()).limit(limit)).scalars().all()
        return [
            {
                "ts": r.ts.isoformat(),
                "student_id": r.student_id,
                "func_name": r.func_name,
                "args_json": r.args_json,
                "result_json": r.result_json,
                "error": r.error,
            }
            for r in rows
        ]