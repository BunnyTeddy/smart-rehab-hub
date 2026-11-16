"""Local durability and bounded latest-frame handoff; no model/network imports."""
import json
import sqlite3
import threading
import time

def dumps(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(',', ':'))

class LatestSlot:
    def __init__(self):
        self.condition = threading.Condition()
        self.value = None
        self.version = 0
        self.closed = False
        self.error = None

    def put(self, value):
        with self.condition:
            self.version += 1
            self.value = value
            self.condition.notify_all()

    def get(self, after=0, timeout=1):
        with self.condition:
            self.condition.wait_for(lambda: self.version > after or self.closed, timeout)
            return (self.version, self.value) if self.version > after else (after, None)

    def close(self, error=None):
        with self.condition:
            self.closed, self.error = True, error
            self.condition.notify_all()

class Journal:
    def __init__(self, path):
        self.lock = threading.RLock()
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.execute('CREATE TABLE IF NOT EXISTS outbox (path TEXT PRIMARY KEY, payload TEXT NOT NULL, sent INTEGER NOT NULL DEFAULT 0)')
        self.db.execute('CREATE TABLE IF NOT EXISTS transport (at_ms INTEGER, path TEXT, ok INTEGER, duration_ms REAL, error TEXT)')
        self.db.commit()

    def enqueue(self, path, value):
        payload = dumps(value)
        with self.lock:
            old = self.db.execute('SELECT payload FROM outbox WHERE path=?', (path,)).fetchone()
            if old and old[0] != payload:
                raise ValueError('Immutable event ID reused with different payload')
            self.db.execute('INSERT OR IGNORE INTO outbox(path,payload) VALUES (?,?)', (path, payload))
            self.db.commit()

    def pending(self, limit=1):
        with self.lock:
            return [(p, json.loads(v)) for p, v in self.db.execute('SELECT path,payload FROM outbox WHERE sent=0 ORDER BY rowid LIMIT ?', (limit,))]

    def acknowledge(self, path):
        with self.lock:
            self.db.execute('UPDATE outbox SET sent=1 WHERE path=?', (path,))
            self.db.commit()

    def record_send(self, path, ok, duration_ms, error=None):
        with self.lock:
            self.db.execute('INSERT INTO transport VALUES (?,?,?,?,?)', (time.time_ns()//1000000, path, int(ok), duration_ms, error))
            self.db.commit()

    def remaining(self):
        with self.lock:
            return self.db.execute('SELECT count(*) FROM outbox WHERE sent=0').fetchone()[0]

    def close(self):
        self.db.close()
