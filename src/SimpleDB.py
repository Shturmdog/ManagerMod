# named_db.py
import sqlite3

class SimpleDB:
    def __init__(self, db_path="database.sqlite", table_name="items"):
        self.db_path = db_path
        self.table_name = table_name
        self._init_table()

    def _init_table(self):
        with self._get_connection() as conn:
            conn.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.table_name} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL
                )
            """)

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def add(self, name: str) -> int | None:
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    f"INSERT INTO {self.table_name} (name) VALUES (?)",
                    (name,)
                )
                return cursor.lastrowid
        except sqlite3.IntegrityError:
            return None

    def delete_id(self, id: int) -> bool:
        with self._get_connection() as conn:
            cursor = conn.execute(
                f"DELETE FROM {self.table_name} WHERE id = ?", (id,)
            )
            return cursor.rowcount > 0

    def delete_name(self, name: str) -> bool:
        with self._get_connection() as conn:
            cursor = conn.execute(
                f"DELETE FROM {self.table_name} WHERE name = ?", (name,)
            )
            return cursor.rowcount > 0

    def get_id(self, name: str) -> int | None:
        with self._get_connection() as conn:
            cursor = conn.execute(
                f"SELECT id FROM {self.table_name} WHERE name = ?", (name,)
            )
            row = cursor.fetchone()
            return row[0] if row else None

    def get_name(self, id: int) -> str | None:
        with self._get_connection() as conn:
            cursor = conn.execute(
                f"SELECT name FROM {self.table_name} WHERE id = ?", (id,)
            )
            row = cursor.fetchone()
            return row[0] if row else None

    def list_all(self):
        with self._get_connection() as conn:
            cursor = conn.execute(f"SELECT id, name FROM {self.table_name}")
            return cursor.fetchall()

    def close(self):
        pass  # соединения закрываются автоматически через контекстный менеджер
