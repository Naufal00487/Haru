import sqlite3
import threading
import logging
from config import ADMIN_ID, LOG_FILE

logger = logging.getLogger("HaruDatabase")

class HaruDatabase:
    def __init__(self, db_path="haru_terminal.db"):
        self.db_path = db_path
        self.lock = threading.Lock() # Fix: Lock global untuk sinkronisasi (Tinggi - Poin 4)
        self._bootstrap()

    def _bootstrap(self):
        """Inisialisasi tabel jika belum ada."""
        query = """
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            lang TEXT DEFAULT 'id',
            is_admin INTEGER DEFAULT 0,
            joined_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(query)
                # Auto-set Admin dari config
                conn.execute(
                    "INSERT OR IGNORE INTO users (user_id, is_admin) VALUES (?, 1)", 
                    (ADMIN_ID,)
                )
                conn.commit()
        logger.info("🗄️ Database bootstrapped successfully.")

    def get_user_lang(self, user_id):
        """Ambil bahasa user dengan thread-safe."""
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                res = conn.execute("SELECT lang FROM users WHERE user_id = ?", (user_id,)).fetchone()
                return res[0] if res else "id"

    def update_user_lang(self, user_id, lang):
        """Update atau daftarkan user baru secara atomic."""
        query = "INSERT INTO users (user_id, lang) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET lang = excluded.lang"
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(query, (user_id, lang))
                conn.commit()

    def is_authorized(self, user_id, whitelist):
        """Cek apakah user ada di whitelist atau terdaftar sebagai admin di DB."""
        if user_id in whitelist:
            return True
        
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                res = conn.execute("SELECT is_admin FROM users WHERE user_id = ?", (user_id,)).fetchone()
                return bool(res[0]) if res else False

# Singleton instance untuk dipakai di seluruh app
db = HaruDatabase()



