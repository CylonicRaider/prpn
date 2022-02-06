
import time

import flask

def init_schema(curs):
    curs.execute('CREATE TABLE IF NOT EXISTS applications ('
                     'user INTEGER PRIMARY KEY REFERENCES allUsers '
                         'ON DELETE CASCADE, '
                     'timestamp REAL NOT NULL, '
                     'content TEXT, '
                     'comments TEXT, '
                     'revealAt REAL'
                 ')')

def handle_get(user_info, app_info):
    now = time.time()
    may_write = (app_info['content'] is None)
    if app_info['revealAt'] is None or now >= app_info['revealAt']:
        comments = app_info['comments']
    else:
        comments = None
    if user_info['user_status'] >= 2:
        if app_info['timestamp'] is None:
            status, status_class, may_write = 'FINISHED', None, None
        else:
            status, status_class = 'ACCEPTED', 'success'
    elif user_info['user_status'] == 0 or comments is not None:
        status, status_class = 'REJECTED', 'warning'
    elif app_info['content'] is not None:
        status, status_class = 'PENDING', 'info'
    else:
        status, status_class = None, None
    return flask.render_template('content/apply.html', status=status,
        status_class=status_class, may_write=may_write, comments=comments)

def handle_post(user_info, app_info, app):
    action = flask.request.form.get('action', 'apply')
    if action == 'check':
        user_info.update(app.prpn.reload_user_info())
        return
    elif action == 'finish':
        db = app.prpn.get_database()
        db.update('DELETE FROM applications WHERE user = ?',
                  (user_info['user_id'],))
        return flask.redirect(flask.url_for('index'))
    text = flask.request.form.get('text', '')
    if not text and app_info['content'] is None:
        flask.flash('Submitting an application is mandatory', 'error')
        return
    elif len(text) > 4096:
        flask.flash('Application is too long', 'error')
        return
    elif text and app_info['content'] is not None:
        flask.flash('Your application is already being processed', 'error')
        return
    now = time.time()
    db = app.prpn.get_database()
    ok = db.update('UPDATE applications SET timestamp = ?, content = ?, '
                       'comments = NULL WHERE user = ?',
                   (now, text, user_info['user_id']))
    if not ok:
        db.update('INSERT INTO applications(user, timestamp, content) '
                      'VALUES (?, ?, ?)',
                  (user_info['user_id'], now, text))
    app_info.update(timestamp=now, content=text)

def register_at(app):
    @app.route('/apply', methods=('GET', 'POST'))
    def application():
        user_info = app.prpn.get_user_info()
        if not user_info['logged_in']: return flask.abort(404)
        db = app.prpn.get_database()
        app_info = db.query('SELECT * FROM applications WHERE user = ?',
                            (user_info['user_id'],))
        if app_info is None:
            app_info = {'timestamp': None, 'content': None, 'comments': None,
                        'revealAt': None}
        if flask.request.method == 'POST':
            result = handle_post(user_info, app_info, app)
            if result is not None:
                return result
        return handle_get(user_info, app_info)
