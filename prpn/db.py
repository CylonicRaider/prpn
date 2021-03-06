
import atexit
import contextlib
import sqlite3
import threading

# No, we do not except enough request load for database serialization to
# matter.

class Database:
    def __init__(self, path, init, **kwargs):
        self.path = path
        self.conn = sqlite3.connect(path, **kwargs)
        self.conn.row_factory = sqlite3.Row
        self.curs = self.conn.cursor()
        self._transactions = 0
        self._is_exclusive = False
        self.init()
        if init is not None: init(self)

    def __enter__(self):
        if self._transactions == 0:
            self.conn.__enter__()
        self._transactions += 1
        return self

    def __exit__(self, *exc_info):
        self._transactions -= 1
        if self._transactions == 0:
            self._is_exclusive = False
            self.conn.__exit__(*exc_info)

    @contextlib.contextmanager
    def transaction(self, exclusive=False):
        if exclusive and self._transactions and not self._is_exclusive:
            raise RuntimeError('Already inside a transaction')
        with self:
            if exclusive and not self._is_exclusive:
                self.curs.execute('BEGIN EXCLUSIVE')
                self._is_exclusive = True
            yield self

    def init(self):
        self.curs.execute('PRAGMA foreign_keys = ON')

    def query(self, query, params=()):
        self.curs.execute(query, params)
        return self.curs.fetchone()

    def query_many(self, query, params=()):
        self.curs.execute(query, params)
        return self.curs.fetchall()

    def insert(self, query, params=()):
        with self.transaction():
            self.curs.execute(query, params)
            return self.curs.lastrowid

    def update(self, query, params=()):
        with self.transaction():
            self.curs.execute(query, params)
            return self.curs.rowcount

    def update_many(self, query, params):
        with self.transaction():
            self.curs.executemany(query, params)
            return self.curs.rowcount

    def close(self):
        self.conn.close()

class LockedDatabase:
    def __init__(self, path, init_schema=None):
        self.path = path
        self.init_schema = init_schema
        self.db = None
        self.lock = threading.RLock()

    def _init(self):
        self.db = Database(self.path, self.init_schema,
                           check_same_thread=False)
        self.db._parent = self

    def acquire(self):
        self.lock.acquire()
        if self.db is None:
            self._init()
        return self.db

    def release(self):
        self.lock.release()

    def close(self):
        db, self.db = self.db, None
        if db is not None: db.close()

    @contextlib.contextmanager
    def transaction(self, *args, **kwargs):
        with self as db:
            with db.transaction(*args, **kwargs):
                yield db

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
            ref._parent.release()

    def register_to(self, app, namespace):
        atexit.register(self.close)
        app.teardown_appcontext(lambda exc: self.put(namespace))
        return lambda: self.get(namespace)
