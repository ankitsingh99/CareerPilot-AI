import hashlib
import json
import aiosqlite
from typing import Optional, Dict, Any

class DatabaseManager:
    """Asynchronous SQLite Cache & Application State Manager."""
    def __init__(self, db_path: str = "database/cache.db"):
        self.db_path = db_path

    async def init_db(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS job_cache (
                    job_hash TEXT PRIMARY KEY,
                    job_id TEXT,
                    source TEXT,
                    title TEXT,
                    company TEXT,
                    location TEXT,
                    fit_score INTEGER,
                    status TEXT,
                    tailored_payload TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            await db.commit()

    @staticmethod
    def generate_hash(title: str, company: str, description: str) -> str:
        raw_string = f"{title.lower()}:{company.lower()}:{description.lower()}"
        return hashlib.sha256(raw_string.encode('utf-8')).hexdigest()

    async def is_processed(self, job_hash: str) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT 1 FROM job_cache WHERE job_hash = ?", (job_hash,)) as cursor:
                return await cursor.fetchone() is not None

    async def save_job(self, job_hash: str, job_id: str, source: str, title: str, company: str, location: str, fit_score: int, status: str, payload: Dict[str, Any]):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT OR REPLACE INTO job_cache (job_hash, job_id, source, title, company, location, fit_score, status, tailored_payload)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (job_hash, job_id, source, title, company, location, fit_score, status, json.dumps(payload)))
            await db.commit()
