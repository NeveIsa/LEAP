
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

from sqlalchemy import create_engine, String, Integer, DateTime, Text, select, Sequence, asc, desc, delete, and_, distinct
from sqlalchemy.exc import OperationalError
from sqlalchemy.dialects import sqlite
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

# Configure logging to a file if enabled
if os.environ.get("ENABLE_SQL_LOGGING", "false").lower() in ("true", "1", "t"):
    logging.basicConfig(filename='sql_debug.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logging.info("SQL logging is enabled.")

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

class Storage:
    def __init__(self, db_path: str):
        # Ensure parent directory exists so DuckDB can create the file
        try:
            db_dir = os.path.dirname(os.path.abspath(db_path))
            if db_dir and not os.path.isdir(db_dir):
                os.makedirs(db_dir, exist_ok=True)
        except Exception:
            # Non-fatal; connecting will still raise if path truly invalid
            pass

        # If a stale WAL exists from a previous DB instance, DuckDB may fail
        # to deserialize (e.g., version/format mismatch). Rename it aside
        # to allow a clean open; the backup can be inspected or removed later.
        try:
            wal_path = f"{db_path}.wal"
            if os.path.isfile(wal_path):
                bak_path = f"{wal_path}.bak"
                # Avoid clobbering an existing backup
                if os.path.exists(bak_path):
                    ts = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
                    bak_path = f"{wal_path}.bak.{ts}"
                os.replace(wal_path, bak_path)
                print(f"Warning: Detected WAL at '{wal_path}'. Renamed to '{bak_path}' to avoid deserialization issues.")
        except Exception:
            # Non-fatal; proceed to attempt open regardless
            pass

        self.engine = create_engine(f"duckdb:///{db_path}", future=True)
        self.SessionLocal = sessionmaker(bind=self.engine, expire_on_commit=False, future=True)
        self.init_db()

    def init_db(self) -> None:
        """Create tables if missing and apply basic migrations.
        If the database file is incompatible/corrupt (e.g., stale WAL was applied,
        or a different DuckDB version), back it up and reinitialize a fresh DB so
        the server can start.
        """
        try:
            Base.metadata.create_all(self.engine)
        except OperationalError as e:
            msg = str(e)
            if "Failed to deserialize" in msg or "field id mismatch" in msg:
                try:
                    # Backup the problematic DB and WAL, then recreate
                    # Get the database file path from the engine URL robustly
                    db_path = getattr(self.engine.url, 'database', None) or ''
                    if not os.path.isabs(db_path):
                        db_path = os.path.abspath(db_path)
                    if db_path and os.path.isfile(db_path):
                        ts = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
                        bak = f"{db_path}.corrupt.{ts}"
                        os.replace(db_path, bak)
                        print(f"Warning: DuckDB could not open DB (deserialize). Backed up to '{bak}' and reinitializing a fresh DB.")
                    wal = f"{db_path}.wal"
                    if wal and os.path.isfile(wal):
                        try:
                            os.remove(wal)
                        except Exception:
                            pass
                    # Recreate engine and init
                    self.engine = create_engine(f"duckdb:///{db_path}", future=True)
                    self.SessionLocal.configure(bind=self.engine)
                    Base.metadata.create_all(self.engine)
                except Exception:
                    raise
            else:
                raise
        # Basic migration: add experiment_name to logs if missing
        try:
            with self.engine.connect() as conn:
                cols = conn.exec_driver_sql("PRAGMA table_info('logs')").fetchall()
                names = {row[1] for row in cols} if cols else set()
                if 'experiment_name' not in names:
                    conn.exec_driver_sql("ALTER TABLE logs ADD COLUMN experiment_name VARCHAR NULL")
        except Exception:
            # Best-effort migration; ignore if PRAGMA not supported or other errors
            pass

    def add_student(self, student_id: str, name: str, email: Optional[str] = None) -> None:
        """Idempotent insert of a student."""
        with self.SessionLocal() as s:
            if not s.get(Student, student_id):
                s.add(Student(student_id=student_id, name=name, email=email))
                s.commit()

    def student_exists(self, student_id: str) -> bool:
        with self.SessionLocal() as s:
            return s.get(Student, student_id) is not None

    def list_students(self) -> List[Dict[str, Any]]:
        """Returns a list of all registered students."""
        with self.SessionLocal() as s:
            students = s.execute(select(Student).order_by(Student.student_id)).scalars().all()
            print(f"Found {len(students)} students in the database.")
            return [
                {"student_id": s.student_id, "name": s.name, "email": s.email}
                for s in students
            ]

    def delete_student(self, student_id: str) -> bool:
        """Deletes a student and all their associated logs. Returns True if deleted, False otherwise."""
        with self.SessionLocal() as s:
            student = s.get(Student, student_id)
            if student:
                # Delete logs first
                s.execute(delete(Log).where(Log.student_id == student_id))
                # Then delete the student
                s.delete(student)
                s.commit()
                return True
            return False

    def log_event(self, *, student_id: str, experiment_name: Optional[str], func_name: str, args_json: str, result_json: Optional[str], error: Optional[str]) -> None:
        with self.SessionLocal() as s:
            s.add(Log(student_id=student_id, experiment_name=experiment_name, func_name=func_name, args_json=args_json, result_json=result_json, error=error))
            try:
                s.commit()
            except Exception as e:
                # If the DB is missing the experiment_name column (older schema), try to migrate on the fly once
                msg = str(e).lower()
                s.rollback()
                if "experiment_name" in msg and "does not have a column" in msg:
                    try:
                        self.init_db()
                        s.add(Log(student_id=student_id, experiment_name=experiment_name, func_name=func_name, args_json=args_json, result_json=result_json, error=error))
                        s.commit()
                        return
                    except Exception:
                        s.rollback()
                # Re-raise original error if migration or retry didn't work
                raise

    def fetch_logs(
        self,
        *,
        student_id: Optional[str] = None,
        experiment_name: Optional[str] = None,
        n: int = 100,
        order: str = "latest",
        start_time: Optional[datetime.datetime] = None,
        end_time: Optional[datetime.datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch logs with optional filtering, ordering, and limit."""
        with self.SessionLocal() as s:
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
            if logging.getLogger().hasHandlers():
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

    def distinct_students_with_logs(self) -> List[str]:
        """Return distinct student_ids that have at least one log, sorted."""
        with self.SessionLocal() as s:
            rows = s.execute(select(distinct(Log.student_id)).order_by(asc(Log.student_id))).all()
            return [r[0] for r in rows if r and r[0]]

    def distinct_experiments(self) -> List[str]:
        """Return distinct non-null experiment_name values from logs, sorted."""
        with self.SessionLocal() as s:
            rows = s.execute(select(distinct(Log.experiment_name)).where(Log.experiment_name.is_not(None)).order_by(asc(Log.experiment_name))).all()
            return [r[0] for r in rows if r and r[0]]
