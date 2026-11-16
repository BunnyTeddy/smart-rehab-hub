"""Durable local commands and outbox; all identifiers survive process restarts."""
import json
import sqlite3
import threading
from pathlib import Path
from .protocol import dumps


class Store:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS commands (id TEXT PRIMARY KEY, acknowledgement TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS outbox (id INTEGER PRIMARY KEY AUTOINCREMENT, path TEXT NOT NULL UNIQUE, payload TEXT NOT NULL);
        ''')
        self.db.commit()

    def get(self, key, default=None):
        with self.lock:
            row = self.db.execute('SELECT value FROM kv WHERE key=?', (key,)).fetchone()
            return json.loads(row[0]) if row else default

    def set(self, key, value):
        with self.lock:
            self.db.execute('INSERT OR REPLACE INTO kv VALUES (?,?)', (key, dumps(value)))
            self.db.commit()

    def acknowledgement(self, command_id):
        with self.lock:
            row = self.db.execute('SELECT acknowledgement FROM commands WHERE id=?', (command_id,)).fetchone()
            return json.loads(row[0]) if row else None

    def accept(self, command_id, acknowledgement, active=None):
        """Record command acceptance and active session in one SQLite transaction."""
        with self.lock, self.db:
            self.db.execute('INSERT INTO commands VALUES (?,?)', (command_id, dumps(acknowledgement)))
            if active is not None:
                self.db.execute('INSERT OR REPLACE INTO kv VALUES (?,?)', ('active', dumps(active)))
                self.db.execute('INSERT OR REPLACE INTO kv VALUES (?,?)', ('progress', '{}'))

    def enqueue(self, path, payload, *, replace=False):
        with self.lock, self.db:
            old = self.db.execute('SELECT payload FROM outbox WHERE path=?', (path,)).fetchone()
            encoded = dumps(payload)
            if old and old[0] != encoded and not replace:
                raise ValueError('immutable_outbox_collision')
            if old and replace:
                self.db.execute('UPDATE outbox SET payload=? WHERE path=?', (encoded, path))
            elif not old:
                self.db.execute('INSERT INTO outbox(path,payload) VALUES (?,?)', (path, encoded))

    def pending(self):
        with self.lock:
            row = self.db.execute('SELECT id,path,payload FROM outbox ORDER BY id LIMIT 1').fetchone()
            return (row[0], row[1], json.loads(row[2])) if row else None

    def sent(self, item):
        with self.lock, self.db:
            # Do not delete a newer replacement written during the network request.
            self.db.execute('DELETE FROM outbox WHERE id=? AND payload=?', (item[0], dumps(item[2])))

    def count(self):
        with self.lock:
            return self.db.execute('SELECT COUNT(*) FROM outbox').fetchone()[0]

    def rep_checkpoint(self, path, event, progress):
        with self.lock, self.db:
            self.db.execute('INSERT INTO outbox(path,payload) VALUES (?,?)', (path, dumps(event)))
            self.db.execute('INSERT OR REPLACE INTO kv VALUES (?,?)', ('progress', dumps(progress)))

    def complete_session(self, summary_path, summary, index_path, index):
        """One commit: crash sees either an active session or its immutable result."""
        with self.lock, self.db:
            old = self.db.execute('SELECT payload FROM outbox WHERE path=?', (summary_path,)).fetchone()
            if old and old[0] != dumps(summary):
                raise ValueError('immutable_summary_collision')
            self.db.execute('INSERT OR IGNORE INTO outbox(path,payload) VALUES (?,?)', (summary_path, dumps(summary)))
            # Reinsert final index after the summary, even when a running index was pending.
            self.db.execute('DELETE FROM outbox WHERE path=?', (index_path,))
            self.db.execute('INSERT INTO outbox(path,payload) VALUES (?,?)', (index_path, dumps(index)))
            self.db.execute('INSERT OR REPLACE INTO kv VALUES (?,?)', ('last_summary', dumps(summary)))
            self.db.execute('INSERT OR REPLACE INTO kv VALUES (?,?)', ('active', 'null'))

    def close(self):
        with self.lock:
            self.db.close()
