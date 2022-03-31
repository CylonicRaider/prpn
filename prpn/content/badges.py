
import math

import flask

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
    result = [{'id': r['badge'], 'label': get_label(r['badge']),
               'amount': r['amount']} for r in rows]
    result.sort(key=lambda entry: get_sort_key(entry['id']))
    return result

def register_at(app):
    @app.route('/store/badges')
    @app.prpn.requires_auth(2)
    def badge_store():
        user_info = app.prpn.get_user_info()
        db = app.prpn.get_database()
        points_row = db.query('SELECT points FROM users WHERE id = ?',
                              (user_info['user_id'],))
        cur_balance = points_row['points'] if points_row is not None else 0
        owned_badges = dict(db.query_many(
            'SELECT badge, amount FROM badges WHERE user = ? AND amount > 0',
            (user_info['user_id'],)
        ))
        badge_groups = {}
        for bid, desc in BADGE_DEFS.items():
            group = ('free' if desc[2] == 0 else
                     'normal' if desc[2] is not None else
                     None)
            if group is None:
                continue
            record = {'id': bid, 'label': desc[0], 'price': desc[2],
                      'limit': desc[3], 'owned': owned_badges.get(bid, 0)}
            record['available'] = (math.inf if record['limit'] is None else
                                   max(record['limit'] - record['owned'], 0))
            try:
                badge_groups[group].append(record)
            except KeyError:
                badge_groups[group] = [record]
        return flask.render_template('content/badges.html',
            cur_balance=cur_balance, badges=badge_groups)
