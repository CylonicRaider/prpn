
import atexit
import sqlite3
import threading

# No, we do not except enough request load for database serialization to
# matter.

class Database:
    def __init__(self, path, **kwargs):
        self.path = path
        self.conn = sqlite3.connect(path, **kwargs)
        self.curs = self.conn.cursor()
        self.init()

    def init(self):
        self.conn.row_factory = sqlite3.Row
        self.curs.execute('PRAGMA foreign_keys = ON')

    def query(self, query, params=()):
        self.curs.execute(query, params)
        return self.curs.fetchone()

    def query_many(self, query, params=()):
        self.curs.execute(query, params)
        return self.curs.fetchall()

    def update(self, query, params=()):
        with self.conn:
            self.curs.execute(query, params)
            return self.curs.lastrowid

    def update_many(self, query, params):
        with self.conn:
            self.curs.executemany(query, params)

    def close(self):
        self.conn.close()

class LockedDatabase:
    def __init__(self, path):
        self.db = Database(path, check_same_thread=False)
        self.lock = threading.RLock()
        self.db._lock = self

    def acquire(self):
        self.lock.acquire()
        return self.db

    def release(self):
        self.lock.release()

    def close(self):
        self.db.close()

    def __enter__(self):
        return self.acquire()

    def __exit__(self, *exc_info):
        self.release()

    def get(self, context):
        if '_DB' not in context:
            context._DB = self.acquire()
        return context._DB

    def put(self, context):
        ref = context.pop('_DB', None)
        if ref is not None:
            ref._lock.release()

    def register_to(self, app, namespace):
        atexit.register(self.close)
        app.teardown_appcontext(lambda exc: self.put(namespace))
        return lambda: self.get(namespace)
