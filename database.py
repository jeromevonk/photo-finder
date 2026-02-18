import sqlite3
import threading
import numpy as np
from config import DATABASE_PATH


class Database:
    def __init__(self):
        self._lock = threading.Lock()
        self.conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        self._create_tables()

    def _create_tables(self):
        cursor = self.conn.cursor()

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS persons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            embedding BLOB
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS photos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT UNIQUE,
            file_size INTEGER,
            last_modified INTEGER
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS faces (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            photo_id INTEGER,
            embedding BLOB,
            FOREIGN KEY(photo_id) REFERENCES photos(id)
        )
        """)

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_photos_path ON photos(file_path)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_faces_photo_id ON faces(photo_id)")

        self.conn.commit()

    # ------------------------------------------------------------------
    # SETTINGS
    # ------------------------------------------------------------------
    def set_setting(self, key, value):
        with self._lock:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT INTO settings (key, value)
                VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value
            """, (key, value))
            self.conn.commit()

    def get_setting(self, key):
        with self._lock:
            cursor = self.conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key=?", (key,))
            row = cursor.fetchone()
            return row[0] if row else None

    # ------------------------------------------------------------------
    # PERSONS
    # ------------------------------------------------------------------
    def add_person(self, name, embedding):
        with self._lock:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT INTO persons (name, embedding)
                VALUES (?, ?)
            """, (name, embedding.tobytes()))
            self.conn.commit()

    def get_persons(self):
        with self._lock:
            cursor = self.conn.cursor()
            cursor.execute("SELECT id, name FROM persons ORDER BY name")
            return cursor.fetchall()

    def get_person_embedding(self, person_id):
        with self._lock:
            cursor = self.conn.cursor()
            cursor.execute("SELECT embedding FROM persons WHERE id=?", (person_id,))
            row = cursor.fetchone()
            if row:
                return np.frombuffer(row[0], dtype=np.float32)
            return None

    # ------------------------------------------------------------------
    # PHOTOS
    # ------------------------------------------------------------------
    def add_photo(self, path, size, mtime):
        with self._lock:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT INTO photos (file_path, file_size, last_modified)
                VALUES (?, ?, ?)
            """, (path, size, mtime))
            self.conn.commit()
            return cursor.lastrowid

    def update_photo_path(self, old_path, new_path):
        with self._lock:
            cursor = self.conn.cursor()
            cursor.execute("""
                UPDATE photos SET file_path=?
                WHERE file_path=?
            """, (new_path, old_path))
            self.conn.commit()

    def find_photo_by_fingerprint(self, file_size, last_modified):
        """Busca foto por size+mtime para detectar arquivos movidos.

        Retorna (file_path,) ou None.
        """
        with self._lock:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT file_path FROM photos
                WHERE file_size=? AND last_modified=?
            """, (file_size, last_modified))
            return cursor.fetchone()

    def remove_missing_photos(self, existing_paths):
        """Remove do banco fotos que não existem mais no disco.

        Usa batch delete para performance.
        """
        with self._lock:
            cursor = self.conn.cursor()
            cursor.execute("SELECT file_path FROM photos")
            db_paths = {row[0] for row in cursor.fetchall()}

            missing = db_paths - existing_paths
            if not missing:
                return

            placeholders = ",".join("?" for _ in missing)
            missing_list = list(missing)

            cursor.execute(
                f"DELETE FROM faces WHERE photo_id IN "
                f"(SELECT id FROM photos WHERE file_path IN ({placeholders}))",
                missing_list,
            )
            cursor.execute(
                f"DELETE FROM photos WHERE file_path IN ({placeholders})",
                missing_list,
            )
            self.conn.commit()

    def get_all_photos(self):
        with self._lock:
            cursor = self.conn.cursor()
            cursor.execute("SELECT file_path, file_size, last_modified FROM photos")
            return cursor.fetchall()

    def get_photo_count(self):
        """Retorna quantidade de fotos indexadas."""
        with self._lock:
            cursor = self.conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM photos")
            return cursor.fetchone()[0]

    def get_person_count(self):
        """Retorna quantidade de pessoas cadastradas."""
        with self._lock:
            cursor = self.conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM persons")
            return cursor.fetchone()[0]

    # ------------------------------------------------------------------
    # FACES
    # ------------------------------------------------------------------
    def add_face(self, photo_id, embedding):
        with self._lock:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT INTO faces (photo_id, embedding)
                VALUES (?, ?)
            """, (photo_id, embedding.tobytes()))
            self.conn.commit()

    def get_all_face_embeddings(self):
        with self._lock:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT faces.embedding, photos.file_path
                FROM faces
                JOIN photos ON faces.photo_id = photos.id
            """)
            rows = cursor.fetchall()

        embeddings = []
        paths = []

        for emb_blob, path in rows:
            embeddings.append(np.frombuffer(emb_blob, dtype=np.float32))
            paths.append(path)

        if embeddings:
            embeddings = np.vstack(embeddings)
        else:
            embeddings = np.empty((0, 512), dtype=np.float32)

        return embeddings, paths
