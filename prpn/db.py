
import atexit
import sqlite3
import threading

# No, we do not except enough request load for database serialization to
# matter.

class LockedDatabase:
    def __init__(self, path):
        self.path = path
        self.db = sqlite3.connect(path)
        self.lock = threading.RLock()

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
            context['_DB'] = self.acquire()
        return context['_DB']

    def put(self, context):
        ref = context.pop('_DB', None)
        if ref is not None:
            ref.release()

    def register_to(self, app, namespace):
        atexit.register(self.close)
        app.teardown_appcontext(lambda exc: self.put(namespace))
        return lambda: self.get(namespace)
