
import math

import click
import flask

# ID: (Label, Sort hint, Buy-yourself cost, Buy-yourself limit, Description)
BADGE_DEFS = {
    'noob': ('Noob', 0, 0, 1,
        'Found the Badge Store and chose to get this badge'),
    'badge': ('Badge', 99, None, None,
        '?'),
    'magic': ('Magic', 100, None, None,
        '???'),
    't1': ('Bronze', 1, 10, None,
        'Had 10 printing points to spend'),
    't2': ('Silver', 1, 100, None,
        'Had 100 printing points to spend'),
    't3': ('Gold', 1, 1000, None,
        'Had 1K printing points to spend'),
    't4': ('Platinum', 1, 10000, None,
        'Had 10K printing points to spend'),
    't5': ('Diamond', 1, 100000, None,
        'Had 100K printing points to spend'),
    't6': ('Unobtainium', 1, 1000000, None,
        'Had 1M printing points to spend'),
}

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
def get_description(bid):
    return get_trait(bid, 4, None)

def get_user_badges(db, uid):
    rows = db.query_many('SELECT * FROM badges WHERE user = ? AND amount > 0',
                         (uid,))
    result = [{'id': r['badge'], 'label': get_label(r['badge']),
               'description': get_description(r['badge']),
               'amount': r['amount']} for r in rows]
    result.sort(key=lambda entry: get_sort_key(entry['id']))
    return result

def add_user_badges(db, uid, badge, amount):
    with db.transaction(True):
        ok = db.update('UPDATE badges SET amount = amount + ? '
                           'WHERE user = ? AND badge = ?',
                       (amount, uid, badge))
        if not ok:
            db.insert('INSERT INTO badges(user, badge, amount) '
                          'VALUES (?, ?, ?)',
                      (uid, badge, amount))

def handle_get(user_info, db):
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
                  'limit': desc[3], 'description': desc[4],
                  'owned': owned_badges.get(bid, 0)}
        record['available'] = (math.inf if record['limit'] is None else
                               max(record['limit'] - record['owned'], 0))
        try:
            badge_groups[group].append(record)
        except KeyError:
            badge_groups[group] = [record]
    total_available = {group: sum(r['available'] for r in records)
                       for group, records in badge_groups.items()}
    return flask.render_template('content/badges.html',
        cur_balance=cur_balance, badges=badge_groups,
        total_available=total_available)

def handle_post(user_info, db):
    action = flask.request.form.get('action')
    if action != 'buy':
        return flask.abort(400)
    bid = flask.request.form.get('badge')
    if not bid or bid not in BADGE_DEFS:
        return flask.abort(400)
    definition = BADGE_DEFS[bid]
    price, limit = definition[2:4]
    if price is None:
        flask.flash('This badge is not for sale', 'error')
        return flask.redirect(flask.url_for('badge_store'), 303)
    with db.transaction(True):
        if limit is not None:
            row = db.query('SELECT amount FROM badges '
                               'WHERE user = ? AND badge = ?',
                           (user_info['user_id'], bid))
            if row is not None and row['amount'] >= limit:
                msg = ('You already have this badge' if limit == 1 else
                       'You may not buy further copies of this badge')
                flask.flash(msg, 'error')
                return flask.redirect(flask.url_for('badge_store'), 303)
        deducted = db.update('UPDATE allUsers SET points = points - ? '
                                 'WHERE id = ? AND points >= ?',
                             (price, user_info['user_id'], price))
        if not deducted:
            flask.flash('Insufficient funds', 'error')
            return flask.redirect(flask.url_for('badge_store'), 303)
        add_user_badges(db, user_info['user_id'], bid, 1)
        flask.flash('Acquisition succeeded', 'success')
        return flask.redirect(flask.url_for('badge_store'), 303)

def get_index_info(user_info, db):
    owned_badges = dict(db.query_many(
        'SELECT badge, amount FROM badges WHERE user = ? AND amount > 0',
        (user_info['user_id'],)
    ))
    available = 0
    for bid, desc in BADGE_DEFS.items():
        if desc[2] != 0: continue
        available += max(desc[3] - owned_badges.get(bid, 0), 0)
    return {'badges_available': available}

def register_at(app):
    @app.cli.command('add-badges',
                     help='Add (positive or negative) amounts of the given '
                          'badge to the given user')
    @click.argument('name')
    @click.argument('badge')
    @click.argument('amount', type=int)
    def set_user_level(name, badge, amount):
        with app.prpn.get_database().transaction(True) as db:
            uid_row = db.query('SELECT id FROM users WHERE name = ?', (name,))
            if not uid_row:
                raise ValueError('Unrecognized user {!r}'.format(name))
            add_user_badges(db, uid_row['id'], badge, amount)
            print('OK')

    @app.route('/store/badges', methods=('GET', 'POST'))
    @app.prpn.requires_auth(2)
    def badge_store():
        user_info = app.prpn.get_user_info()
        db = app.prpn.get_database()
        if flask.request.method == 'POST':
            result = handle_post(user_info, db)
            if result is not None:
                return result
        return handle_get(user_info, db)
