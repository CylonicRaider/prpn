
import time
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

class Scheduler:
    def __init__(self, db, logger):
        self.db = db
        self.logger = logger
        self.commands = {}
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

    def register(self, cmd, callback):
        self.commands[cmd] = callback

    def schedule(self, cmd, params, timestamp=None, serial=False):
        if timestamp is None: timestamp = time.time()
        with self.db.transaction(True):
            if serial:
                queued = self.db.query('SELECT 1 FROM scheduled '
                                           'WHERE type = ? LIMIT 1',
                                       (cmd,))
                if queued: return
            self.db.insert('INSERT INTO scheduled(type, params, nextRun, '
                                                 'gcAt) '
                               'VALUES (?, ?, ?, ?)',
                           (cmd, json.dumps(params), timestamp,
                            timestamp + UNKNOWN_EXPIRE))
        with self._cond:
            self._cond.notify_all()

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

    def _next_task(self, now):
        row = self.db.query('SELECT * FROM scheduled ORDER BY nextRun '
                            'LIMIT 1')
        if row is None:
            return (None, now + IDLE_PAUSE)
        elif row['nextRun'] > now:
            return (None, row['nextRun'])
        else:
            return (row, now)

    def _run(self):
        wait_until = time.time()
        while 1:
            with self._cond:
                if not self._busy:
                    self._thread = None
                    break
                now = time.time()
                if now < wait_until:
                    self._cond.wait(wait_until - now)
            with self.db.transaction(True):
                row, wait_until = self._next_task()
                if row is None:
                    continue
                params = json.loads(row['params'])
                ok, next_run = self.run_scheduled(row['type'], params,
                                                  row['nextRun'], row['gcAt'])
                if next_run is None:
                    self.db.update('DELETE FROM scheduled WHERE id = ?',
                                   (row['id'],))
                elif ok:
                    self.db.update('UPDATE scheduled SET nextRun = ?, '
                                                        'gcAt = ? '
                                       'WHERE id = ?',
                                   (next_run, next_run + UNKNOWN_EXPIRE,
                                    row['id']))
                else:
                    self.db.update('UPDATE scheduled SET nextRun = ? '
                                       'WHERE id = ?',
                                   (next_run, row['id']))
                next_row, wait_until = self._next_task()
