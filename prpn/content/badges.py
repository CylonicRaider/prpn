
import math

# ID: (Label, Sort hint, Buy-yourself cost, Buy-yourself limit)
BADGE_DEFS = {'noob': ('Noob', 0, None, 1), 'magic': ('Magic', 0, None, None)}

def init_schema(curs):
    curs.execute('CREATE TABLE IF NOT EXISTS badges ('
                     'user INTEGER REFERENCES allUsers ON DELETE CASCADE, '
                     'badge TEXT NOT NULL, '
                     'amount INTEGER NOT NULL DEFAULT 0, '
                     'PRIMARY KEY (user, badge)'
                 ')')

def get_trait(bid, key, default):
    try:
        return BADGE_DEFS[bid][key]
    except KeyError:
        return default
def get_label(bid):
    return get_trait(bid, 0, bid)
def get_sort_key(bid):
    return (get_trait(bid, 1, math.inf), bid)

def get_user_badges(db, uid):
    rows = db.query_many('SELECT * FROM badges WHERE user = ? AND amount > 0',
                         (uid,))
    result = [(r['badge'], get_label(r['badge']), r['amount']) for r in rows]
    result.sort(key=lambda entry: get_sort_key(entry[0]))
    return result

def register_at(app):
    # Nothing yet.
    pass
