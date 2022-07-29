
import time
import random

import flask

from .. import tmplutil

PAGE_SIZE = 10

RANDOM = random.SystemRandom()

MANDATORY_ITEMS = (
    ('id', 'ID', 'an ID'),
    ('motivation', 'Motivation statement', 'a motivation statement')
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
    curs.execute('CREATE INDEX IF NOT EXISTS applications_timestamp '
                     'ON applications(timestamp)')
    curs.execute('CREATE VIEW IF NOT EXISTS pendingApplications AS '
                     'SELECT id AS uid, name AS name, '
                            'timestamp AS timestamp, content AS content, '
                            'comments AS comments '
                     'FROM applications JOIN allUsers ON user = id '
                     'WHERE content IS NOT NULL AND comments IS NULL')
    curs.execute('CREATE VIEW IF NOT EXISTS allApplications AS '
                     'SELECT id AS uid, name AS name, status AS userStatus, '
                            'timestamp AS timestamp, content AS content, '
                            'comments AS comments, revealAt AS revealAt '
                     'FROM applications JOIN allUsers ON user = id')

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
    may_write = (user_info['user_status'] == 1 and
                 status in (None, 'REJECTED'))
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
    elif action != 'apply':
        return flask.abort(400)
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
    now = time.time()
    offset = tmplutil.get_request_int64p('offset')
    criterion = flask.request.args.get('filter') or 'PENDING'
    sort = flask.request.args.get('sort') or 'submitted'
    if criterion == 'PENDING':
        filter_sql = ('WHERE content IS NOT NULL AND comments IS NULL')
    elif criterion == 'RESOLVED':
        filter_sql = ('WHERE content IS NULL OR comments IS NOT NULL')
    elif criterion == 'ACCEPTED':
        filter_sql = ('WHERE userStatus >= 2')
    elif criterion == 'REJECTED':
        filter_sql = ('WHERE content IS NULL AND comments IS NOT NULL')
    elif criterion == 'REJECTED_HIDDEN':
        filter_sql = ('WHERE content IS NULL AND comments IS NOT NULL '
                          'AND :now < revealAt')
    elif criterion == 'REJECTED_PUBLIC':
        filter_sql = ('WHERE content IS NULL AND comments IS NOT NULL '
                          'AND (revealAt IS NULL OR :now >= revealAt)')
    else: # Preferred spelling: ALL
        filter_sql = ''
    if sort == 'id':
        order_sql = 'uid ASC'
    elif sort == '-id':
        order_sql = 'uid DESC'
    elif sort == 'name':
        order_sql = 'LOWER(name) ASC, name ASC'
    elif sort == '-name':
        order_sql = 'LOWER(name) DESC, name DESC'
    elif sort == '-submitted':
        order_sql = 'timestamp DESC'
    else: # Preferred spelling: submitted
        order_sql = 'timestamp ASC'
    db = app.prpn.get_database()
    entries = db.query_many('SELECT * FROM allApplications ' + filter_sql +
            ' ORDER BY ' + order_sql + ' LIMIT :limit OFFSET :offset',
        {'limit': PAGE_SIZE + 1, 'offset': offset, 'now': now})
    has_more = (len(entries) > PAGE_SIZE)
    entries = [dict(e, status=get_application_status(e, now))
               for e in entries[:PAGE_SIZE]]
    return flask.render_template('content/apply-review-list.html',
        entries=entries, offset=offset, amount=PAGE_SIZE, has_more=has_more)

def handle_review_get(uid, app):
    now = time.time()
    entry = app.prpn.get_database().query('SELECT * FROM allApplications '
                                              'WHERE uid = ?',
                                          (uid,))
    if entry is not None:
        entry = dict(entry, status=get_application_status(entry, now))
    return flask.render_template('content/apply-review.html', entry=entry,
        mandatory_items=MANDATORY_ITEMS, prohibited_items=PROHIBITED_ITEMS)

def handle_review_post(uid, app):
    form = flask.request.form
    action = form.get('action', 'none')
    db = app.prpn.get_database()
    if action == 'accept':
        with db:
            db.update('UPDATE applications SET content = NULL, '
                                              'comments = NULL, '
                                              'revealAt = ? '
                          'WHERE user = ?',
                      (time.time(), uid))
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
        reveal_at = time.time()
        if reveal_delay:
            if form.get('delay-randomize'):
                reveal_delay *= RANDOM.random()
            reveal_at += reveal_delay
        comments = format_rejection_comments(form)
        db.update('UPDATE applications SET content = NULL, comments = ?, '
                                          'revealAt = ? '
                      'WHERE user = ?',
                  (comments, reveal_at, uid))
        return flask.redirect(flask.url_for('application_review_list'))
    elif action == 'reject-permanent':
        if not form.get('confirm-reject-permanent'):
            flask.flash('Rejection with prejudice requires confirmation',
                        'warning')
            return None
        with db:
            db.update('DELETE FROM applications WHERE user = ?', (uid,))
            db.update('UPDATE allUsers SET status = 0 '
                          'WHERE id = ? AND status <= 1',
                      (uid,))
        return flask.redirect(flask.url_for('application_review_list'))

def get_application_status(eai, now):
    level, reveal_at = eai['userStatus'], eai['revealAt']
    if level >= 2:
        return 'ACCEPTED'
    elif eai['content'] is not None and eai['comments'] is None:
        return 'PENDING'
    elif reveal_at is None or now >= reveal_at:
        return 'REJECTED_PUBLIC'
    else:
        return 'REJECTED_HIDDEN'

def get_application_counts(db):
    def len_to_str(rows):
        l = len(rows)
        return '10+' if l > 10 else str(l) if l else ''

    now = time.time()
    pending = len_to_str(db.query_many(
        'SELECT 1 FROM pendingApplications LIMIT 11'
    ))
    accepted = len_to_str(db.query_many(
        'SELECT 1 FROM applications JOIN users ON id = user LIMIT 11'
    ))
    rejected_hidden = len_to_str(db.query_many(
        'SELECT 1 '
        'FROM applications '
        'WHERE comments IS NOT NULL AND revealAt > ? '
        'LIMIT 11',
        (now,)
    ))
    rejected_public = len_to_str(db.query_many(
        'SELECT 1 '
        'FROM applications '
        'WHERE comments IS NOT NULL AND (revealAt IS NULL OR revealAt <= ?)'
        'LIMIT 11',
        (now,)
    ))

    return {'pending': pending,
            'accepted': accepted,
            'rejected_hidden': rejected_hidden,
            'rejected_public': rejected_public}

def get_index_info(user_info, db):
    app_row = db.query('SELECT 1 FROM applications WHERE user = ?',
                       (user_info['user_id'],))
    result = {'has_application': bool(app_row)}
    if user_info['user_status'] >= 3:
        result['app_counts'] = get_application_counts(db)
    return result

def register_at(app):
    @app.route('/apply', methods=('GET', 'POST'))
    @app.prpn.requires_auth(0)
    def application():
        user_info = app.prpn.get_user_info()
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

    @app.route('/apply/sample')
    @app.prpn.requires_auth(0)
    def application_sample():
        return flask.render_template('content/apply-sample.html')

    @app.route('/apply/review')
    @app.prpn.requires_auth(3)
    def application_review_list():
        return handle_review_list(app)

    @app.route('/apply/review/<int:uid>', methods=('GET', 'POST'))
    @app.prpn.requires_auth(3)
    def application_review(uid):
        if flask.request.method == 'POST':
            result = handle_review_post(uid, app)
            if result is not None:
                return result
        return handle_review_get(uid, app)
