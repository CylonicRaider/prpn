
import sqlite3

import flask

def init_schema(curs):
    curs.execute('CREATE TABLE IF NOT EXISTS lottery ('
                     'user INTEGER PRIMARY KEY REFERENCES allUsers '
                         'ON DELETE CASCADE, '
                     'awarded INTEGER NOT NULL DEFAULT 0, '
                     'totalAwarded INTEGER NOT NULL DEFAULT 0'
                 ')')

def handle_get(user_info, lot_data):
    enrolled = (lot_data is not None)
    awarded = lot_data['awarded'] if enrolled else 0
    total_awarded = lot_data['totalAwarded'] if enrolled else 0
    return flask.render_template('content/lottery.html',
        enrolled=enrolled, awarded=awarded, total_awarded=total_awarded)

def handle_post(app, user_info):
    action = flask.request.form.get('action', 'none')
    if action == 'reset-counter':
        app.prpn.get_database().update('UPDATE lottery SET awarded = 0 '
                                           'WHERE user = ?',
                                       (user_info['user_id'],))
        flask.flash('Awarded printing point counter reset', 'info')
    elif action == 'join':
        db = app.prpn.get_database()
        with db.transaction(True):
            funds_row = db.query('SELECT points FROM users WHERE id = ?',
                                 (user_info['user_id'],))
            if not funds_row or funds_row['points'] < 1:
                flask.flash('Insufficient funds', 'error')
                return None
            try:
                db.update('INSERT INTO lottery(user) VALUES (?)',
                          (user_info['user_id'],))
            except sqlite3.IntegrityError:
                flask.flash('You are already enrolled into the '
                            'Printing Point Lottery', 'info')
            else:
                db.update('UPDATE allUsers SET points = points - 1 '
                              'WHERE id = ?',
                          (user_info['user_id'],))
                flask.flash('Printing Point Lottery enrollment successful',
                            'success')
    elif action == 'leave':
        changed = app.prpn.get_database().update('DELETE FROM lottery '
                                                     'WHERE user = ?',
                                                 (user_info['user_id'],))
        if changed:
            flask.flash('You have left the Printing Point Lottery', 'success')
        else:
            flask.flash('You are not enrolled into the '
                        'Printing Point Lottery', 'info')

def register_at(app):
    @app.route('/lottery', methods=('GET', 'POST'))
    @app.prpn.requires_auth(0)
    def lottery():
        user_info = app.prpn.get_user_info()
        if flask.request.method == 'POST':
            result = handle_post(app, user_info)
            if result is not None:
                return result
        lot_data = app.prpn.get_database().query('SELECT * FROM lottery '
                                                     'WHERE user = ?',
                                                 (user_info['user_id'],))
        return handle_get(user_info, lot_data)
