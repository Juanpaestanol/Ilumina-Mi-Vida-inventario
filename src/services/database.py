import os
import sqlite3
import libsql_experimental as libsql
import streamlit as st

DB_PATH = "ilumina.db"


class TursoCursorWrapper:
    """Cursor wrapper que reconecta automáticamente si el stream de Turso caduca

    y convierte parámetros a tuplas para evitar TypeErrors.
    """

    def __init__(self, conn_wrapper, cursor):
        self.conn_wrapper = conn_wrapper
        self._cursor = cursor

    def _is_stream_expired(self, exc: Exception) -> bool:
        msg = str(exc).lower()
        return any(
            err in msg
            for err in (
                "stream not found",
                "stream_not_found",
                "404",
                "hrana",
                "closed",
                "broken pipe",
            )
        )

    def _prepare_args(self, args, kwargs):
        clean_args = []
        for a in args:
            if isinstance(a, list):
                clean_args.append(tuple(a))
            else:
                clean_args.append(a)

        if "params" in kwargs and isinstance(kwargs["params"], list):
            kwargs["params"] = tuple(kwargs["params"])

        return clean_args, kwargs

    def execute(self, sql, *args, **kwargs):
        clean_args, clean_kwargs = self._prepare_args(args, kwargs)
        try:
            return self._cursor.execute(sql, *clean_args, **clean_kwargs)
        except Exception as e:
            if self._is_stream_expired(e):
                self.conn_wrapper._reconnect()
                self._cursor = self.conn_wrapper._conn.cursor()
                return self._cursor.execute(sql, *clean_args, **clean_kwargs)
            raise e

    def executescript(self, sql):
        try:
            return self._cursor.executescript(sql)
        except Exception as e:
            if self._is_stream_expired(e):
                self.conn_wrapper._reconnect()
                self._cursor = self.conn_wrapper._conn.cursor()
                return self._cursor.executescript(sql)
            raise e

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()

    def fetchmany(self, size=None):
        return (
            self._cursor.fetchmany(size) if size else self._cursor.fetchmany()
        )

    @property
    def description(self):
        return self._cursor.description

    @property
    def rowcount(self):
        return self._cursor.rowcount

    @property
    def lastrowid(self):
        return self._cursor.lastrowid

    def close(self):
        try:
            self._cursor.close()
        except Exception:
            pass

    def __getattr__(self, name):
        return getattr(self._cursor, name)


class TursoConnectionWrapper:
    """Connection wrapper para gestionar reconexiones transparentes con Turso."""

    def __init__(self, db_url, auth_token):
        self.db_url = db_url
        self.auth_token = auth_token
        self._conn = None
        self._reconnect()

    def _reconnect(self):
        try:
            if self._conn:
                self._conn.close()
        except Exception:
            pass
        self._conn = libsql.connect(
            database=self.db_url,
            auth_token=self.auth_token,
        )

    def _is_stream_expired(self, exc: Exception) -> bool:
        msg = str(exc).lower()
        return any(
            err in msg
            for err in (
                "stream not found",
                "stream_not_found",
                "404",
                "hrana",
                "closed",
                "broken pipe",
            )
        )

    def cursor(self):
        try:
            return TursoCursorWrapper(self, self._conn.cursor())
        except Exception as e:
            if self._is_stream_expired(e):
                self._reconnect()
                return TursoCursorWrapper(self, self._conn.cursor())
            raise e

    def execute(self, *args, **kwargs):
        cur = self.cursor()
        return cur.execute(*args, **kwargs)

    def executescript(self, *args, **kwargs):
        cur = self.cursor()
        return cur.executescript(*args, **kwargs)

    def commit(self):
        try:
            return self._conn.commit()
        except Exception as e:
            if self._is_stream_expired(e):
                self._reconnect()
                return self._conn.commit()
            raise e

    def rollback(self):
        try:
            return self._conn.rollback()
        except Exception as e:
            if self._is_stream_expired(e):
                self._reconnect()
                return self._conn.rollback()
            raise e

    def close(self):
        if self._conn:
            try:
                self._conn.close()
            except Exception:
                pass

    def __getattr__(self, name):
        return getattr(self._conn, name)


class Database:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        turso_url = st.secrets.get(
            "TURSO_DATABASE_URL", os.getenv("TURSO_DATABASE_URL")
        )
        turso_token = st.secrets.get(
            "TURSO_AUTH_TOKEN", os.getenv("TURSO_AUTH_TOKEN")
        )

        if turso_url and turso_token:
            self.conn = TursoConnectionWrapper(turso_url, turso_token)
        else:
            self.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
            self.conn.execute("PRAGMA foreign_keys = ON")

        self._create_tables()
        self._migrate_schema()

    def _create_tables(self):
        cursor = self.conn.cursor()
        cursor.executescript("""
            CREATE TABLE IF NOT EXISTS Materials (
                Id INTEGER PRIMARY KEY AUTOINCREMENT,
                Name TEXT UNIQUE NOT NULL COLLATE NOCASE,
                Deleted INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS Locations (
                Id TEXT PRIMARY KEY NOT NULL,
                Name TEXT NOT NULL,
                Deleted INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS Items (
                Id TEXT PRIMARY KEY NOT NULL,
                MaterialId INTEGER NOT NULL,
                Description TEXT,
                Price REAL NOT NULL CHECK(Price >= 0),
                Stock INTEGER NOT NULL DEFAULT 0 CHECK(Stock >= 0),
                TotalSold INTEGER NOT NULL DEFAULT 0,
                Ganancias REAL DEFAULT 0.0,
                CreatedDate TEXT NOT NULL,
                ImageData BLOB,
                ThumbnailData BLOB,
                Deleted INTEGER DEFAULT 0,
                FOREIGN KEY (MaterialId) REFERENCES Materials(Id) ON DELETE RESTRICT
            );

            CREATE TABLE IF NOT EXISTS History (
                Id INTEGER PRIMARY KEY AUTOINCREMENT,
                Timestamp TEXT NOT NULL,
                User TEXT NOT NULL,
                ActionType TEXT NOT NULL,
                TargetType TEXT NOT NULL,
                TargetId TEXT NOT NULL,
                Quantity INTEGER,
                LocationId TEXT,
                Note TEXT,
                OldValues TEXT,
                NewValues TEXT,
                OriginalId INTEGER,
                Superseded INTEGER DEFAULT 0,
                GananciasDelta REAL,
                FOREIGN KEY (LocationId) REFERENCES Locations(Id) ON UPDATE CASCADE ON DELETE SET NULL
            );

            CREATE INDEX IF NOT EXISTS idx_history_timestamp ON History(Timestamp);
            CREATE INDEX IF NOT EXISTS idx_history_target ON History(TargetType, TargetId);
            CREATE INDEX IF NOT EXISTS idx_history_action ON History(ActionType);
            CREATE INDEX IF NOT EXISTS idx_history_original ON History(OriginalId);
            CREATE INDEX IF NOT EXISTS idx_history_superseded ON History(Superseded);
        """)
        self.conn.commit()

    def _migrate_schema(self):
        cursor = self.conn.cursor()
        cursor.execute("PRAGMA table_info(Items)")
        columns = [row[1] for row in cursor.fetchall()]
        if "Deleted" not in columns:
            cursor.execute("ALTER TABLE Items ADD COLUMN Deleted INTEGER DEFAULT 0")
            self.conn.commit()

        cursor.execute("PRAGMA table_info(History)")
        columns = [row[1] for row in cursor.fetchall()]
        if "Superseded" not in columns:
            cursor.execute(
                "ALTER TABLE History ADD COLUMN Superseded INTEGER DEFAULT 0"
            )
            self.conn.commit()

        cursor.execute("PRAGMA table_info(Materials)")
        columns = [row[1] for row in cursor.fetchall()]
        if "Deleted" not in columns:
            cursor.execute(
                "ALTER TABLE Materials ADD COLUMN Deleted INTEGER DEFAULT 0"
            )
            self.conn.commit()

        cursor.execute("PRAGMA table_info(Locations)")
        columns = [row[1] for row in cursor.fetchall()]
        if "Deleted" not in columns:
            cursor.execute(
                "ALTER TABLE Locations ADD COLUMN Deleted INTEGER DEFAULT 0"
            )
            self.conn.commit()

        cursor.execute("PRAGMA table_info(Items)")
        columns = [row[1] for row in cursor.fetchall()]
        if "Ganancias" not in columns:
            cursor.execute(
                "ALTER TABLE Items ADD COLUMN Ganancias REAL DEFAULT 0.0"
            )
            self.conn.commit()
            cursor.execute(
                "UPDATE Items SET Ganancias = Price * TotalSold"
            )
            self.conn.commit()

        cursor.execute("PRAGMA table_info(History)")
        columns = [row[1] for row in cursor.fetchall()]
        if "GananciasDelta" not in columns:
            cursor.execute(
                "ALTER TABLE History ADD COLUMN GananciasDelta REAL"
            )
            self.conn.commit()

        cursor.execute("PRAGMA table_info(History)")
        columns = [row[1] for row in cursor.fetchall()]
        if "LogHash" not in columns:
            cursor.execute(
                "ALTER TABLE History ADD COLUMN LogHash TEXT"
            )
            self.conn.commit()

        cursor.execute("UPDATE History SET ActionType = 'CREAR', TargetType = 'MATERIAL' WHERE ActionType = 'ADD_MATERIAL'")
        cursor.execute("UPDATE History SET ActionType = 'MODIFICAR', TargetType = 'MATERIAL' WHERE ActionType = 'EDIT_MATERIAL'")
        cursor.execute("UPDATE History SET ActionType = 'ELIMINAR', TargetType = 'MATERIAL' WHERE ActionType = 'DELETE_MATERIAL'")
        cursor.execute("UPDATE History SET ActionType = 'RESTAURAR', TargetType = 'MATERIAL' WHERE ActionType = 'RESTORE_MATERIAL'")
        
        cursor.execute("UPDATE History SET ActionType = 'CREAR', TargetType = 'LUGAR' WHERE ActionType = 'ADD_LOCATION'")
        cursor.execute("UPDATE History SET ActionType = 'MODIFICAR', TargetType = 'LUGAR' WHERE ActionType = 'EDIT_LOCATION'")
        cursor.execute("UPDATE History SET ActionType = 'ELIMINAR', TargetType = 'LUGAR' WHERE ActionType = 'DELETE_LOCATION'")
        cursor.execute("UPDATE History SET ActionType = 'RESTAURAR', TargetType = 'LUGAR' WHERE ActionType = 'RESTORE_LOCATION'")
        
        cursor.execute("UPDATE History SET ActionType = 'CREAR', TargetType = 'PULSERA' WHERE ActionType = 'ADD_ITEM'")
        cursor.execute("UPDATE History SET ActionType = 'MODIFICAR', TargetType = 'PULSERA' WHERE ActionType = 'EDIT_ITEM'")
        cursor.execute("UPDATE History SET ActionType = 'ELIMINAR', TargetType = 'PULSERA' WHERE ActionType = 'DELETE_ITEM'")
        cursor.execute("UPDATE History SET ActionType = 'RESTAURAR', TargetType = 'PULSERA' WHERE ActionType = 'RESTORE_ITEM'")
        
        cursor.execute("UPDATE History SET ActionType = 'CORREGIR', TargetType = 'TRANSACCION' WHERE ActionType = 'CORRECT_TRANSACTION'")
        cursor.execute("UPDATE History SET ActionType = 'INICIO_SESION', TargetType = 'SEGURIDAD' WHERE ActionType = 'LOGIN'")
        cursor.execute("UPDATE History SET ActionType = 'CIERRE_SESION', TargetType = 'SEGURIDAD' WHERE ActionType = 'LOGOUT'")
        
        cursor.execute("UPDATE History SET ActionType = 'VENTA', TargetType = 'PULSERA' WHERE ActionType = 'VENTA_CORRECTED'")
        cursor.execute("UPDATE History SET ActionType = 'RESURTIDO', TargetType = 'PULSERA' WHERE ActionType = 'RESURTIDO_CORRECTED'")
        cursor.execute("UPDATE History SET ActionType = 'REGALO', TargetType = 'PULSERA' WHERE ActionType = 'REGALO_CORRECTED'")
        cursor.execute("UPDATE History SET ActionType = 'PERDIDA', TargetType = 'PULSERA' WHERE ActionType = 'PERDIDA_CORRECTED'")
        cursor.execute("UPDATE History SET ActionType = 'ALTA', TargetType = 'PULSERA' WHERE ActionType = 'ALTA_CORRECTED'")

        cursor.execute("UPDATE History SET TargetType = 'PULSERA' WHERE ActionType IN ('VENTA', 'RESURTIDO', 'REGALO', 'PERDIDA', 'ALTA') AND (TargetType IS NULL OR TargetType = 'ITEM')")
        self.conn.commit()

        cursor.execute("SELECT COUNT(*) FROM History WHERE LogHash IS NULL")
        null_count = cursor.fetchone()[0]
        if null_count > 0:
            import hashlib
            cursor.execute("""
                SELECT Id, Timestamp, User, ActionType, TargetType, TargetId,
                       Quantity, LocationId, Note, OldValues, NewValues, OriginalId,
                       GananciasDelta
                FROM History
                ORDER BY Id ASC
            """)
            rows = cursor.fetchall()
            prev_hash = ""
            for row in rows:
                r_id, timestamp, user, action_type, target_type, target_id, qty, loc_id, note, old_val, new_val, orig_id, gan_delta = row
                payload = f"{timestamp}|{user}|{action_type}|{target_type}|{target_id}|" \
                          f"{qty or 0}|{loc_id or ''}|{note or ''}|" \
                          f"{old_val or ''}|{new_val or ''}|" \
                          f"{orig_id or 0}|{gan_delta or 0.0}|{prev_hash}"
                h = hashlib.sha256(payload.encode("utf-8")).hexdigest()
                cursor.execute("UPDATE History SET LogHash = ? WHERE Id = ?", (h, r_id))
                prev_hash = h
            self.conn.commit()

        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='Transactions'"
        )
        if cursor.fetchone():
            cursor.execute("DROP TABLE Transactions")
            self.conn.commit()

    def initialize(self):
        self._create_tables()
        self._migrate_schema()

    @property
    def connection(self):
        return self.conn

    def close(self):
        if self.conn:
            self.conn.close()