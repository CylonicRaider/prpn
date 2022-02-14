
import flask

MAX_AMOUNT = 2 ** 63 - 1

def handle_get(user_info, db):
    row = db.query('SELECT points FROM users WHERE id = ?',
                   (user_info['user_id'],))
    cur_balance = None if row is None else row['points']
    return flask.render_template('content/transfer.html',
                                 cur_balance=cur_balance)

def handle_post(user_info, db):
    recipient_type = flask.request.form['recipient-type']
    if recipient_type == 'user':
        recipient = flask.request.form.get('recipient')
        if not recipient:
            flask.flash('Missing recipient', 'error')
            return
    elif recipient_type == 'acs':
        recipient = None
    else:
        return flask.abort(400)
    try:
        amount = int(flask.request.form['amount'], 10)
        if amount < 0 or amount > MAX_AMOUNT:
            raise ValueError('Transfer amount out of range')
    except ValueError:
        return flask.abort(400)
    amount_s = '' if amount == 1 else 's'
    with db.transaction(True):
        sender_row = db.query('SELECT name FROM users WHERE id = ?',
                              (user_info['user_id'],))
        if sender_row is None:
            flask.flash('No such sender user?!', 'error')
            return
        if recipient is not None:
            recipient_row = db.query('SELECT id, name FROM users '
                                         'WHERE name = ?',
                                     (recipient,))
            if recipient_row is None:
                flask.flash('No such recipient user', 'error')
                return
        # After this point, we redirect the user using a 303 redirect to
        # discourage page reloads resulting in resubmitting the request.
        deducted = db.update('UPDATE allUsers SET points = points - ? '
                                 'WHERE id = ? AND status >= 2 AND '
                                       'points >= ?',
                             (amount, user_info['user_id'], amount))
        if not deducted:
            flask.flash('Insufficient funds', 'error')
        elif recipient is None:
            flask.flash('Donated {} printing point{} to Automated '
                            'Campus Security'.format(amount, amount_s),
                        'success')
        else:
            credited = db.update('UPDATE allUsers SET points = points + ? '
                                     'WHERE id = ? AND status >= 2',
                                 (amount, recipient_row['id']))
            if not credited:
                flask.flash('Crediting the recipient failed?!', 'error')
            else:
                flask.flash('Transferred {} printing point{} to user {}'
                                .format(amount, amount_s,
                                        recipient_row['name']),
                            'success')
        return flask.redirect(flask.url_for('transfer'), 303)

def register_at(app):
    @app.route('/transfer', methods=('GET', 'POST'))
    def transfer():
        user_info = app.prpn.get_user_info()
        if not user_info['logged_in'] or user_info['user_status'] < 2:
            return flask.abort(404)
        db = app.prpn.get_database()
        if flask.request.method == 'POST':
            result = handle_post(user_info, db)
            if result is not None:
                return result
        return handle_get(user_info, db)
