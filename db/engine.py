"""Unified Database Engine supporting both PostgreSQL (Supabase) and SQLite."""
import os
import re
import sqlite3
from typing import Optional, Any, List, Dict, Tuple, Union
from config import DB_PATH

_ENGINE = None
_IS_POSTGRES = None


def get_database_url() -> Optional[str]:
    """Retrieve DATABASE_URL from Streamlit secrets, environment variables, or config."""
    # 1. Check Streamlit secrets if available
    try:
        import streamlit as st
        if hasattr(st, "secrets") and "DATABASE_URL" in st.secrets:
            url = str(st.secrets["DATABASE_URL"]).strip()
            if url:
                return url
    except Exception:
        pass

    # 2. Check environment variable
    env_url = os.environ.get("DATABASE_URL")
    if env_url and env_url.strip():
        return env_url.strip()

    return None


def is_postgres() -> bool:
    """Return True if connected to PostgreSQL (Supabase), False for local SQLite."""
    global _IS_POSTGRES
    if _IS_POSTGRES is None:
        url = get_database_url()
        _IS_POSTGRES = bool(url and ("postgres" in url.lower()))
    return _IS_POSTGRES


def normalize_postgres_url(url: str) -> str:
    """Ensure PostgreSQL URI is compatible with SQLAlchemy."""
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return url


def get_engine():
    """Get or create singleton SQLAlchemy Engine."""
    global _ENGINE
    if _ENGINE is None:
        import sqlalchemy as sa
        db_url = get_database_url()
        if db_url:
            norm_url = normalize_postgres_url(db_url)
            _ENGINE = sa.create_engine(
                norm_url,
                pool_pre_ping=True,
                pool_recycle=300,
                pool_size=5,
                max_overflow=10,
            )
        else:
            sqlite_url = f"sqlite:///{DB_PATH}"
            _ENGINE = sa.create_engine(
                sqlite_url,
                connect_args={"check_same_thread": False},
            )
    return _ENGINE


def reset_engine():
    """Reset engine singleton (used when switching credentials or in tests)."""
    global _ENGINE, _IS_POSTGRES
    _ENGINE = None
    _IS_POSTGRES = None


class UnifiedCursor:
    """Wraps cursor/result to provide unified fetchall / fetchone as dictionaries."""

    def __init__(self, result_or_cursor, lastrowid: Optional[int] = None, rowcount: int = 0):
        self._raw = result_or_cursor
        self.lastrowid = lastrowid
        self.rowcount = rowcount

    def fetchall(self) -> List[Dict[str, Any]]:
        if self._raw is None:
            return []
        if hasattr(self._raw, "mappings"):
            return [dict(r) for r in self._raw.mappings().fetchall()]
        elif hasattr(self._raw, "fetchall"):
            rows = self._raw.fetchall()
            return [dict(r) for r in rows]
        return []

    def fetchone(self) -> Optional[Dict[str, Any]]:
        if self._raw is None:
            return None
        if hasattr(self._raw, "mappings"):
            row = self._raw.mappings().fetchone()
            return dict(row) if row else None
        elif hasattr(self._raw, "fetchone"):
            row = self._raw.fetchone()
            return dict(row) if row else None
        return None


class UnifiedConnection:
    """Uniform connection facade supporting both SQLite and PostgreSQL."""

    def __init__(self, conn, is_pg: bool, is_raw_sqlite: bool = False):
        self.conn = conn
        self.is_pg = is_pg
        self.is_raw_sqlite = is_raw_sqlite

    def _convert_query_params(self, sql: str, params: Any) -> Tuple[Any, Any]:
        """Convert '?' style to ':_p0, :_p1' for SQLAlchemy or keep as-is for SQLite DBAPI."""
        import sqlalchemy as sa
        if isinstance(params, (list, tuple)):
            p_dict = {}
            idx = 0
            def repl(match):
                nonlocal idx
                name = f"_p{idx}"
                idx += 1
                return f":{name}"
            converted_sql = re.sub(r'\?', repl, sql)
            for i, val in enumerate(params):
                p_dict[f"_p{i}"] = val
            return sa.text(converted_sql), p_dict
        elif isinstance(params, dict):
            return sa.text(sql), params
        else:
            return sa.text(sql), {}

    def execute(self, sql: str, params: Any = None) -> UnifiedCursor:
        if self.is_raw_sqlite:
            # Native sqlite3 connection
            cur = self.conn.cursor()
            if params is None:
                cur.execute(sql)
            else:
                cur.execute(sql, params)
            return UnifiedCursor(cur, lastrowid=cur.lastrowid, rowcount=cur.rowcount)
        else:
            # SQLAlchemy connection
            stmt, bind_params = self._convert_query_params(sql, params)
            result = self.conn.execute(stmt, bind_params)
            
            # For Postgres INSERT RETURNING id, or default lastrowid
            lastrowid = None
            try:
                if hasattr(result, "inserted_primary_key") and result.inserted_primary_key:
                    lastrowid = result.inserted_primary_key[0]
            except Exception:
                pass

            return UnifiedCursor(result, lastrowid=lastrowid, rowcount=result.rowcount)

    def executemany(self, sql: str, params_list: List[Any]) -> UnifiedCursor:
        if self.is_raw_sqlite:
            cur = self.conn.cursor()
            cur.executemany(sql, params_list)
            return UnifiedCursor(cur, lastrowid=cur.lastrowid, rowcount=cur.rowcount)
        else:
            import sqlalchemy as sa
            stmt = sa.text(sql)
            result = self.conn.execute(stmt, params_list)
            return UnifiedCursor(result, rowcount=result.rowcount)

    def commit(self):
        if hasattr(self.conn, "commit"):
            self.conn.commit()

    def rollback(self):
        if hasattr(self.conn, "rollback"):
            self.conn.rollback()

    def close(self):
        if hasattr(self.conn, "close"):
            self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.rollback()
        else:
            self.commit()
        self.close()


def get_connection() -> UnifiedConnection:
    """Return a unified database connection.
    
    If DATABASE_URL is set, uses SQLAlchemy connection to PostgreSQL.
    If not, falls back to local SQLite with WAL mode.
    """
    if is_postgres():
        engine = get_engine()
        sa_conn = engine.connect()
        return UnifiedConnection(sa_conn, is_pg=True, is_raw_sqlite=False)
    else:
        # Standard high-performance SQLite connection
        conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return UnifiedConnection(conn, is_pg=False, is_raw_sqlite=True)
