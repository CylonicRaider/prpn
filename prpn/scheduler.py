
import time
import json
import threading

IDLE_PAUSE = 300

def init_schema(curs):
    curs.execute('CREATE TABLE IF NOT EXISTS scheduled ('
                     'id INTEGER PRIMARY KEY, '
                     'type TEXT NOT NULL, '
                     'params TEXT NOT NULL, '
                     'nextRun REAL NOT NULL'
                 ')')
    curs.execute('CREATE INDEX IF NOT EXISTS scheduled_type '
                     'ON scheduled(type)')
    curs.execute('CREATE INDEX IF NOT EXISTS scheduled_nextRun '
                     'ON scheduled(nextRun)')

class Scheduler:
    def __init__(self, db):
        self.db = db
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

    def schedule(self, cmd, params, timestamp=None, serial=False):
        if timestamp is None: timestamp = time.time()
        with self.db.transaction(True):
            if serial:
                queued = self.db.query('SELECT 1 FROM scheduled '
                                           'WHERE type = ? LIMIT 1',
                                       (cmd,))
                if queued: return
            self.db.insert('INSERT INTO scheduled(type, params, nextRun) '
                               'VALUES (?, ?, ?)',
                           (cmd, json.dumps(params), timestamp))
        with self._cond:
            self._cond.notify_all()

    def run_scheduled(self, cmd, params, timestamp):
        raise NotImplementedError

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
                next_run = self.run_scheduled(row['type'],
                                              json.loads(row['params']),
                                              row['nextRun'])
                if next_run is None:
                    self.db.update('DELETE FROM scheduled WHERE id = ?',
                                   (row['id'],))
                else:
                    self.db.update('UPDATE scheduled SET nextRun = ? '
                                       'WHERE id = ?',
                                   (next_run, row['id']))
                next_row, wait_until = self._next_task()
