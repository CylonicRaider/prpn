
import time
import random

import flask

PAGE_SIZE = 10
MAX_OFFSET = 2 ** 63 - 1

RANDOM = random.SystemRandom()

MANDATORY_ITEMS = (
    ('cover', 'Cover letter', 'a cover letter'),
    ('id', 'ID', 'an ID or an enrollment certificate'),
    ('acrr', 'ACRR', 'an Approved Citizen Ranking record'),
    ('motivation', 'Motivation letter', 'a motivation letter')
)
PROHIBITED_ITEMS = (
    # These ones I did think of ahead-of-time.
    ('swearing', 'Swearing', 'Swearing'),
    ('misrepresentation', 'Misrepresentation',
         'Misrepresenting your identity'),
    ('nonsense', 'Nonsense', 'Including nonsensical text'),
    # These ones, not.
    ('threatening', 'Threatening', 'Threatening the Printing Point '
         'Management Administration and/or Printing Point Management '
         'Administration staff'),
    ('misunderstanding', 'Misunderstanding', 'Deliberately misunderstanding '
         'the instructions'),
    ('bribery', 'Bribery', 'Attempting to bribe and/or seduce the Printing '
         'Point Management Administration and/or Printing Point Management '
         'Administration staff')
)
ITEM_LINE = ('{} in Mandatory Printing Point Tracking Program applications '
             'is {}.')

def init_schema(curs):
    curs.execute('CREATE TABLE IF NOT EXISTS applications ('
                     'user INTEGER PRIMARY KEY REFERENCES allUsers '
                         'ON DELETE CASCADE, '
                     'timestamp REAL NOT NULL, '
                     'content TEXT, '
                     'comments TEXT, '
                     'revealAt REAL'
                 ')')
    curs.execute('CREATE VIEW IF NOT EXISTS pendingApplications AS '
                     'SELECT id AS uid, name AS name, '
                            'timestamp AS timestamp, content AS content, '
                            'comments AS comments '
                     'FROM applications JOIN allUsers ON user = id '
                     'WHERE content IS NOT NULL AND comments IS NULL')
    curs.execute('CREATE INDEX IF NOT EXISTS applications_timestamp '
                     'ON applications(timestamp)')

def format_rejection_comments(form_data):
    paragraphs = []
    for name, _, description in MANDATORY_ITEMS:
        if not form_data.get('missing-' + name): continue
        paragraphs.append(ITEM_LINE.format('Supplying ' + description,
                                           'mandatory'))
    for name, _, description in PROHIBITED_ITEMS:
        if not form_data.get('prohibited-' + name): continue
        paragraphs.append(ITEM_LINE.format(description, 'prohibited'))
    for para in form_data.get('extra-comments', '').split('\n\n'):
        para = para.strip()
        if not para: continue
        paragraphs.append(para)
    RANDOM.shuffle(paragraphs)
    return '\n\n'.join(paragraphs)

def handle_get(user_info, app_info):
    now = time.time()
    is_revealed = (app_info['revealAt'] is None or
                   now >= app_info['revealAt'])
    comments = app_info['comments'] if is_revealed else None
    may_write = (user_info['user_status'] == 1 and
                 app_info['content'] is None and is_revealed)
    if user_info['user_status'] >= 2:
        if app_info['timestamp'] is None:
            status, status_class = 'FINISHED', None
        else:
            status, status_class = 'ACCEPTED', 'success'
    elif user_info['user_status'] == 0 or comments is not None:
        status, status_class = 'REJECTED', 'warning'
    elif app_info['content'] is not None or app_info['revealAt'] is not None:
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
    if not text:
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
                       'comments = NULL, revealAt = NULL WHERE user = ?',
                   (now, text, user_info['user_id']))
    if not ok:
        db.update('INSERT INTO applications(user, timestamp, content) '
                      'VALUES (?, ?, ?)',
                  (user_info['user_id'], now, text))
    app_info.update(timestamp=now, content=text, comments=None, revealAt=None)

def handle_review_list(app):
    try:
        offset = int(flask.request.args.get('offset', '0'), 10)
        if offset < 0 or offset > MAX_OFFSET:
            raise ValueError('Pagination offset out of range')
    except ValueError:
        return flask.abort(400)
    db = app.prpn.get_database()
    # Getting SQLite to use an appropriate (partial) index for this query is
    # surprisingly annoying. :( Therefore, one should avoid looking at the
    # non-first pages of the application listing. :D
    entries = db.query_many('SELECT uid, name, timestamp '
                                'FROM pendingApplications '
                                'ORDER BY timestamp ASC '
                                'LIMIT ? OFFSET ?',
                            (PAGE_SIZE + 1, offset))
    has_more = (len(entries) > PAGE_SIZE)
    entries = entries[:PAGE_SIZE]
    return flask.render_template('content/apply-review-list.html',
        entries=entries, offset=offset, amount=PAGE_SIZE, has_more=has_more)

def handle_review_get(uid, app):
    entry = app.prpn.get_database().query('SELECT * FROM pendingApplications '
                                              'WHERE uid = ?',
                                          (uid,))
    if entry is None:
        return flask.abort(404)
    return flask.render_template('content/apply-review.html', entry=entry,
        mandatory_items=MANDATORY_ITEMS, prohibited_items=PROHIBITED_ITEMS)

def handle_review_post(uid, app):
    form = flask.request.form
    action = form.get('action', 'none')
    db = app.prpn.get_database()
    if action == 'accept':
        with db:
            db.update('UPDATE applications SET content = NULL, '
                                              'comments = NULL '
                          'WHERE user = ?',
                      (uid,))
            db.update('UPDATE allUsers SET status = 2, points = points + 1 '
                          'WHERE id = ? AND status <= 1',
                      (uid,))
        return flask.redirect(flask.url_for('application_review_list'))
    elif action == 'reject':
        try:
            reveal_delay = (int(form.get('delay-days', '0'), 10) * 86400 +
                            int(form.get('delay-hours', '0'), 10) * 3600 +
                            int(form.get('delay-minutes', '0'), 10) * 60 +
                            int(form.get('delay-seconds', '0'), 10))
            if reveal_delay < 0:
                raise ValueError('Negative reveal delay')
        except ValueError:
            return flask.abort(400)
        if reveal_delay:
            if form.get('delay-randomize'):
                reveal_delay *= RANDOM.random()
            reveal_at = time.time() + reveal_delay
        else:
            reveal_at = None
        comments = format_rejection_comments(form)
        db.update('UPDATE applications SET content = NULL, comments = ?, '
                                          'revealAt = ? '
                      'WHERE user = ?',
                  (comments, reveal_at, uid))
        return flask.redirect(flask.url_for('application_review_list'))
    elif action == 'reject-permanent':
        if not form.get('confirm-reject-permanent'):
            flask.flash('Please confirm rejection with prejudice', 'warning')
            return None
        with db:
            db.update('DELETE FROM applications WHERE user = ?', (uid,))
            db.update('UPDATE allUsers SET status = 0 '
                          'WHERE id = ? AND status <= 1',
                      (uid,))
        return flask.redirect(flask.url_for('application_review_list'))

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
        else:
            app_info = dict(app_info)
        if flask.request.method == 'POST':
            result = handle_post(user_info, app_info, app)
            if result is not None:
                return result
        return handle_get(user_info, app_info)

    @app.route('/apply/review')
    def application_review_list():
        user_info = app.prpn.get_user_info()
        if not user_info['logged_in'] or user_info['user_status'] < 3:
            return flask.abort(404)
        return handle_review_list(app)

    @app.route('/apply/review/<int:uid>', methods=('GET', 'POST'))
    def application_review(uid):
        user_info = app.prpn.get_user_info()
        if not user_info['logged_in'] or user_info['user_status'] < 3:
            return flask.abort(404)
        if flask.request.method == 'POST':
            result = handle_review_post(uid, app)
            if result is not None:
                return result
        return handle_review_get(uid, app)
