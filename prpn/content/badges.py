
import math

# ID: (Label, Sort hint, Buy-yourself cost)
BADGE_DEFS = {'noob': ('Noob', 0, None)}

def init_schema(curs):
    curs.execute('CREATE TABLE IF NOT EXISTS badges ('
                     'user INTEGER REFERENCES allUsers ON DELETE CASCADE, '
                     'badge TEXT NOT NULL, '
                     'amount INTEGER NOT NULL DEFAULT 0, '
                     'PRIMARY KEY (user, badge)'
                 ')')

def get_label(bid):
    try:
        return BADGE_DEFS[bid][0]
    except KeyError:
        return bid

def get_user_badges(db, uid):
    rows = db.query_many('SELECT * FROM badges WHERE user = ? AND amount > 0',
                         (uid,))
    result = [(r['badge'], get_label(r['badge']), r['amount']) for r in rows]
    result.sort(key=lambda entry: (BADGE_DEFS.get(entry[0], math.inf),
                                   entry[0]))
    return result

def register_at(app):
    # Nothing yet.
    pass
