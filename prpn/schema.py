
from . import scheduler
from .content import application

def init_schema(db):
    with db:
        curs = db.curs
        curs.execute('CREATE TABLE IF NOT EXISTS allUsers ('
                         'id INTEGER PRIMARY KEY, '
                         'name TEXT NOT NULL UNIQUE, '
                         # 0 = non-user; 1 = potential user entity; 2 = user;
                         # 3 = privileged user.
                         'status INTEGER NOT NULL DEFAULT 0, '
                         'points INTEGER NOT NULL DEFAULT 0'
                     ')')
        curs.execute('CREATE VIEW IF NOT EXISTS users AS '
                     'SELECT id AS id, name AS name, points AS points '
                         'FROM allUsers '
                         'WHERE status >= 2')
        scheduler.init_schema(curs)
        application.init_schema(curs)
