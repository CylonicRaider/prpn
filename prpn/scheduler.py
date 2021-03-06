
import time
import collections
import functools
import json
import threading

IDLE_PAUSE     =   300
UNKNOWN_RETRY  =   300
UNKNOWN_EXPIRE = 86400

def init_schema(curs):
    curs.execute('CREATE TABLE IF NOT EXISTS scheduled ('
                     'id INTEGER PRIMARY KEY, '
                     'type TEXT NOT NULL, '
                     'params TEXT NOT NULL, '
                     'nextRun REAL NOT NULL, '
                     'gcAt REAL NOT NULL'
                 ')')
    curs.execute('CREATE INDEX IF NOT EXISTS scheduled_type '
                     'ON scheduled(type)')
    curs.execute('CREATE INDEX IF NOT EXISTS scheduled_nextRun '
                     'ON scheduled(nextRun)')

def regular_schedule(period, offset=0, fuzz=1):
    def callback(timestamp):
        return ((timestamp + fuzz) // period + 1) * period + offset

    return callback

class Scheduler:
    def __init__(self, ldb, logger, app=None):
        self.ldb = ldb
        self.logger = logger
        self.app = app
        self.commands = {}
        self._deferred = collections.deque()
        self._cond = threading.Condition()
        self._busy = False
        self._thread = None

    def start(self):
        with self._cond:
            if self._thread is not None: return
            thr = threading.Thread(target=self._run)
            thr.daemon = True
            thr.start()
            self._busy = True
            self._thread = thr

    def stop(self):
        with self._cond:
            self._busy = False

    def join(self):
        with self._cond:
            thr = self._thread
        if thr is not None:
            thr.join()

    def register_ex(self, cmd, callback):
        self.commands[cmd] = callback

    def register(self, cmd, callback):
        @functools.wraps(callback)
        def wrapper(cmd, params, timestamp):
            return callback(params, timestamp)

        self.register_ex(cmd, wrapper)

    def schedule(self, cmd, params=None, timestamp=None, serial=False):
        if timestamp is None: timestamp = time.time()
        with self.ldb.transaction(True) as db:
            if serial:
                queued = db.query('SELECT 1 FROM scheduled WHERE type = ? '
                                      'LIMIT 1',
                                  (cmd,))
                if queued: return
            db.insert('INSERT INTO scheduled(type, params, nextRun, gcAt) '
                          'VALUES (?, ?, ?, ?)',
                      (cmd, json.dumps(params), timestamp,
                       timestamp + UNKNOWN_EXPIRE))
        with self._cond:
            self._cond.notify_all()

    def schedule_later(self, cmd, params=None, timestamp=None, serial=False):
        if timestamp is None: timestamp = time.time()
        with self._cond:
            self._deferred.append(lambda: self.schedule(cmd, params,
                                                        timestamp, serial))
            self._cond.notify_all()

    def register_regular(self, cmd, callback, time_callback):
        @functools.wraps(callback)
        def wrapper(cmd, params, timestamp):
            callback(timestamp)
            return time_callback(timestamp)

        if isinstance(time_callback, (int, float)):
            time_callback = regular_schedule(time_callback)
        elif isinstance(time_callback, (tuple, list)):
            time_callback = regular_schedule(*time_callback)

        with self._cond:
            self.register_ex(cmd, wrapper)
            self.schedule_later(cmd, None, time_callback(time.time()), True)

    def _in_context(self, func, *args, **kwds):
        if self.app is not None:
            with self.app.app_context():
                return func(*args, **kwds)
        else:
            return func(*args, **kwds)

    def run_scheduled(self, cmd, params, timestamp, expires):
        try:
            callback = self.commands[cmd]
        except KeyError:
            if timestamp >= expires:
                self.logger.error('Unrecognized scheduled task type {!r}; '
                    'abandoning'.format(cmd))
                return (False, None)
            else:
                self.logger.warning('Unrecognized scheduled task type {!r}; '
                    'will retry in {}s'.format(cmd, UNKNOWN_RETRY))
                return (False, timestamp + UNKNOWN_RETRY)
        try:
            next_run = callback(cmd, params, timestamp)
        except BaseException:
            self.logger.exception('Error while running scheduled task {!r}; '
                'abandoning'.format(cmd))
            return (False, None)
        return (True, next_run)

    def _next_task(self, db, now):
        row = db.query('SELECT * FROM scheduled ORDER BY nextRun LIMIT 1')
        if row is None:
            return (None, now + IDLE_PAUSE)
        elif row['nextRun'] > now:
            return (None, row['nextRun'])
        else:
            return (row, now)

    def _run(self):
        def_task, wait_until = None, time.time()
        while 1:
            if def_task:
                def_task()
                def_task = None
            with self._cond:
                if not self._busy:
                    self._thread = None
                    break
                if self._deferred:
                    def_task = self._deferred.popleft()
                    continue
                now = time.time()
                if now < wait_until:
                    self._cond.wait(wait_until - now)
                    continue
            with self.ldb.transaction(True) as db:
                row, wait_until = self._next_task(db, now)
                if row is None:
                    continue
                params = json.loads(row['params'])
                ok, next_run = self._in_context(self.run_scheduled,
                    row['type'], params, row['nextRun'], row['gcAt'])
                if next_run is None:
                    db.update('DELETE FROM scheduled WHERE id = ?',
                                   (row['id'],))
                elif ok:
                    db.update('UPDATE scheduled SET nextRun = ?, gcAt = ? '
                                  'WHERE id = ?',
                              (next_run, next_run + UNKNOWN_EXPIRE,
                               row['id']))
                else:
                    db.update('UPDATE scheduled SET nextRun = ? WHERE id = ?',
                              (next_run, row['id']))
                next_row, wait_until = self._next_task(db, now)

    def add_callback_ex(self, name):
        def callback(func):
            self.register_ex(name, func)
            return func

        return callback

    def add_callback(self, name):
        def callback(func):
            self.register(name, func)
            return func

        return callback

    def add_regular(self, name, schedule):
        def callback(func):
            self.register_regular(name, func, schedule)
            return func

        return callback

    def register_at(self, app):
        app.prpn.init_task(self.start)
