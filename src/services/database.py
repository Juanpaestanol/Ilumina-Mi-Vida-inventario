import os
import sqlite3
import libsql_experimental as libsql
import streamlit as st

DB_PATH = "ilumina.db"


class Database:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        # 1. Detectar credenciales de Turso (Secrets de Streamlit Cloud o variables de entorno)
        turso_url = st.secrets.get(
            "TURSO_DATABASE_URL", os.getenv("TURSO_DATABASE_URL")
        )
        turso_token = st.secrets.get(
            "TURSO_AUTH_TOKEN", os.getenv("TURSO_AUTH_TOKEN")
        )

        if turso_url and turso_token:
            # Conexión remota a Turso (Producción en la nube)
            self.conn = libsql.connect(
                database=turso_url,
                auth_token=turso_token,
                check_same_thread=False,
            )
        else:
            # Conexión local a archivo SQLite (Desarrollo en máquina local)
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
        # Add Deleted to Items if missing
        cursor.execute("PRAGMA table_info(Items)")
        columns = [row[1] for row in cursor.fetchall()]
        if "Deleted" not in columns:
            cursor.execute("ALTER TABLE Items ADD COLUMN Deleted INTEGER DEFAULT 0")
            self.conn.commit()

        # Add Superseded to History if missing
        cursor.execute("PRAGMA table_info(History)")
        columns = [row[1] for row in cursor.fetchall()]
        if "Superseded" not in columns:
            cursor.execute(
                "ALTER TABLE History ADD COLUMN Superseded INTEGER DEFAULT 0"
            )
            self.conn.commit()

        # Add Deleted to Materials if missing
        cursor.execute("PRAGMA table_info(Materials)")
        columns = [row[1] for row in cursor.fetchall()]
        if "Deleted" not in columns:
            cursor.execute(
                "ALTER TABLE Materials ADD COLUMN Deleted INTEGER DEFAULT 0"
            )
            self.conn.commit()

        # Add Deleted to Locations if missing
        cursor.execute("PRAGMA table_info(Locations)")
        columns = [row[1] for row in cursor.fetchall()]
        if "Deleted" not in columns:
            cursor.execute(
                "ALTER TABLE Locations ADD COLUMN Deleted INTEGER DEFAULT 0"
            )
            self.conn.commit()

        # Add Ganancias to Items if missing
        cursor.execute("PRAGMA table_info(Items)")
        columns = [row[1] for row in cursor.fetchall()]
        if "Ganancias" not in columns:
            cursor.execute(
                "ALTER TABLE Items ADD COLUMN Ganancias REAL DEFAULT 0.0"
            )
            self.conn.commit()
            # Backfill existing items: Ganancias = Price * TotalSold
            cursor.execute(
                "UPDATE Items SET Ganancias = Price * TotalSold"
            )
            self.conn.commit()

        # Add GananciasDelta to History if missing
        cursor.execute("PRAGMA table_info(History)")
        columns = [row[1] for row in cursor.fetchall()]
        if "GananciasDelta" not in columns:
            cursor.execute(
                "ALTER TABLE History ADD COLUMN GananciasDelta REAL"
            )
            self.conn.commit()

        # Add LogHash to History if missing
        cursor.execute("PRAGMA table_info(History)")
        columns = [row[1] for row in cursor.fetchall()]
        if "LogHash" not in columns:
            cursor.execute(
                "ALTER TABLE History ADD COLUMN LogHash TEXT"
            )
            self.conn.commit()

        # Run taxonomy migration for old history records (idempotent updates)
        # 1. Materials
        cursor.execute("UPDATE History SET ActionType = 'CREAR', TargetType = 'MATERIAL' WHERE ActionType = 'ADD_MATERIAL'")
        cursor.execute("UPDATE History SET ActionType = 'MODIFICAR', TargetType = 'MATERIAL' WHERE ActionType = 'EDIT_MATERIAL'")
        cursor.execute("UPDATE History SET ActionType = 'ELIMINAR', TargetType = 'MATERIAL' WHERE ActionType = 'DELETE_MATERIAL'")
        cursor.execute("UPDATE History SET ActionType = 'RESTAURAR', TargetType = 'MATERIAL' WHERE ActionType = 'RESTORE_MATERIAL'")
        
        # 2. Locations
        cursor.execute("UPDATE History SET ActionType = 'CREAR', TargetType = 'LUGAR' WHERE ActionType = 'ADD_LOCATION'")
        cursor.execute("UPDATE History SET ActionType = 'MODIFICAR', TargetType = 'LUGAR' WHERE ActionType = 'EDIT_LOCATION'")
        cursor.execute("UPDATE History SET ActionType = 'ELIMINAR', TargetType = 'LUGAR' WHERE ActionType = 'DELETE_LOCATION'")
        cursor.execute("UPDATE History SET ActionType = 'RESTAURAR', TargetType = 'LUGAR' WHERE ActionType = 'RESTORE_LOCATION'")
        
        # 3. Items (Pulseras)
        cursor.execute("UPDATE History SET ActionType = 'CREAR', TargetType = 'PULSERA' WHERE ActionType = 'ADD_ITEM'")
        cursor.execute("UPDATE History SET ActionType = 'MODIFICAR', TargetType = 'PULSERA' WHERE ActionType = 'EDIT_ITEM'")
        cursor.execute("UPDATE History SET ActionType = 'ELIMINAR', TargetType = 'PULSERA' WHERE ActionType = 'DELETE_ITEM'")
        cursor.execute("UPDATE History SET ActionType = 'RESTAURAR', TargetType = 'PULSERA' WHERE ActionType = 'RESTORE_ITEM'")
        
        # 4. Corrections and other events
        cursor.execute("UPDATE History SET ActionType = 'CORREGIR', TargetType = 'TRANSACCION' WHERE ActionType = 'CORRECT_TRANSACTION'")
        cursor.execute("UPDATE History SET ActionType = 'INICIO_SESION', TargetType = 'SEGURIDAD' WHERE ActionType = 'LOGIN'")
        cursor.execute("UPDATE History SET ActionType = 'CIERRE_SESION', TargetType = 'SEGURIDAD' WHERE ActionType = 'LOGOUT'")
        
        # 5. Core actions for corrected transactions (VENTA_CORRECTED -> VENTA, etc.)
        cursor.execute("UPDATE History SET ActionType = 'VENTA', TargetType = 'PULSERA' WHERE ActionType = 'VENTA_CORRECTED'")
        cursor.execute("UPDATE History SET ActionType = 'RESURTIDO', TargetType = 'PULSERA' WHERE ActionType = 'RESURTIDO_CORRECTED'")
        cursor.execute("UPDATE History SET ActionType = 'REGALO', TargetType = 'PULSERA' WHERE ActionType = 'REGALO_CORRECTED'")
        cursor.execute("UPDATE History SET ActionType = 'PERDIDA', TargetType = 'PULSERA' WHERE ActionType = 'PERDIDA_CORRECTED'")
        cursor.execute("UPDATE History SET ActionType = 'ALTA', TargetType = 'PULSERA' WHERE ActionType = 'ALTA_CORRECTED'")

        # 6. Set TargetType to PULSERA for existing inventory actions
        cursor.execute("UPDATE History SET TargetType = 'PULSERA' WHERE ActionType IN ('VENTA', 'RESURTIDO', 'REGALO', 'PERDIDA', 'ALTA') AND (TargetType IS NULL OR TargetType = 'ITEM')")
        self.conn.commit()

        # 7. Backfill hashes for existing history records if any have NULL hashes
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

        # Drop old Transactions table if it exists
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