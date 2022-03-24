
import flask

from .. import tmplutil
from ..auth import STATUS_TO_NAME, STATUS_TO_SHORT_NAME

PAGE_SIZE = 10

VISIBILITY_DESCS = (
    (2, 'public', 'Public', 'everyone can see your profile'),
    (0, 'private', 'Private', 'only you can see your profile')
)

VISIBILITY_TO_NAME = {0: 'Private', 1: 'Friends only', 2: 'Public'}

SUBMIT_DESCS = (
    ('display-name', 'displayName', 64, 'Display name'),
    ('visibility', None, {d[1]: d[0] for d in VISIBILITY_DESCS},
     'Visibility'),
    ('description', None, 4096, 'Description')
)

def init_schema(curs):
    curs.execute('CREATE TABLE IF NOT EXISTS userProfiles ('
                     'user INTEGER PRIMARY KEY REFERENCES allUsers '
                         'ON DELETE CASCADE, '
                     # 0 = private; 1 = protected (err, Friends only, where
                     # Friendship is NYI); 2 = public (to all Users).
                     'visibility INTEGER NOT NULL DEFAULT 0, '
                     'displayName TEXT, '
                     'description TEXT'
                 ')')

def handle_user_list(db):
    criterion = flask.request.args.get('filter', 'ALL')
    if criterion == 'USER':
        filter_sql = 'WHERE status >= 2'
    elif criterion == 'USER_REGULAR':
        filter_sql = 'WHERE status = 2'
    elif criterion == 'USER_ENHANCED':
        filter_sql = 'WHERE status = 3'
    elif criterion == 'NONUSER':
        filter_sql = 'WHERE status <= 1'
    elif criterion == 'NONUSER_PENDING':
        filter_sql = 'WHERE status = 1'
    elif criterion == 'NONUSER_FINAL':
        filter_sql = 'WHERE status = 0'
    else:
        filter_sql = ''
    offset = tmplutil.get_request_int64p('offset')
    entries = db.query_many('SELECT id, name, status, points, '
                                   'EXISTS(SELECT * FROM pendingApplications '
                                          'WHERE uid = id) AS hasApplication '
                                'FROM allUsers ' + filter_sql +
                                ' ORDER BY name ASC LIMIT ? OFFSET ?',
                            (PAGE_SIZE + 1, offset))
    has_more = (len(entries) > PAGE_SIZE)
    entries = [dict(e,
                    statusName=STATUS_TO_NAME[e['status']],
                    shortStatusName=STATUS_TO_SHORT_NAME[e['status']])
               for e in entries[:PAGE_SIZE]]
    return flask.render_template('content/user-list.html', entries=entries,
        offset=offset, amount=PAGE_SIZE, has_more=has_more)

def handle_user_get(name, acc_info, db):
    profile_row = db.query('SELECT * FROM allUsers '
                               'LEFT JOIN userProfiles ON id = user '
                               'WHERE status >= 2 AND name = ?',
                           (name,))
    if profile_row is None:
        profile_data = {'id': None, 'visibility': -1}
    else:
        profile_data = dict(profile_row)
        profile_data.pop('user', None)
    visibility = profile_data['visibility'] or 0
    if visibility < 2 and not (acc_info['user_id'] == profile_data['id'] or
                               acc_info['user_status'] >= 3 and
                                   visibility >= 0 and
                                   flask.request.args.get('force')):
        profile_data = {
            'visible': False,
            'visibility': visibility
        }
    else:
        profile_data.update(
            visible=True,
            visibility=visibility,
            visibilityName=VISIBILITY_TO_NAME[visibility],
            statusName=STATUS_TO_NAME[profile_data['status']],
            shortStatusName=STATUS_TO_SHORT_NAME[profile_data['status']]
        )
    if not profile_data.get('displayName'):
        profile_data['displayName'] = name
    may_edit = (profile_data['visible'] and (
        acc_info['user_id'] == profile_data['id'] or
        acc_info['user_status'] >= 3
    ))
    return flask.render_template('content/user.html', profile_name=name,
                                 profile_data=profile_data, may_edit=may_edit,
                                 all_visibilities=VISIBILITY_DESCS)

def handle_user_post(name, user_info, db):
    profile_name = flask.request.form.get('user')
    if not profile_name:
        return flask.abort(400)
    assignments = []
    for propname, colname, limit, description in SUBMIT_DESCS:
        colname = colname or propname
        value = flask.request.form.get(propname)
        if value is None:
            continue
        elif isinstance(limit, int):
            if len(value) > limit:
                flask.flash(description + ' is too long', 'error')
                return None
            elif not value:
                value = None
            assignments.append((colname, value))
        elif isinstance(limit, dict):
            if value not in limit:
                flask.flash(description + ' invalid', 'error')
                return None
            assignments.append((colname, limit[value]))
        else:
            raise AssertionError('')
    if not assignments:
        return None
    with db.transaction(True):
        row = db.query('SELECT id FROM users WHERE name = ?', (profile_name,))
        if not row:
            flask.flash('No such user', 'error')
            return None
        profile_id = row['id']
        if not (profile_id == user_info['user_id'] or
                user_info['user_status'] >= 3):
            flask.flash('Permission denied', 'error')
            return None
        sql = 'UPDATE userProfiles SET {} WHERE user = :uid'.format(
            ', '.join('{} = :{}'.format(a[0], a[0]) for a in assignments)
        )
        values = dict(assignments, uid=profile_id)
        ok = db.update(sql, values)
        if not ok:
            sql = ('INSERT INTO userProfiles (user{}) VALUES (:uid{})'
                   .format(
                ''.join(', {}'.format(a[0])  for a in assignments),
                ''.join(', :{}'.format(a[0]) for a in assignments)
            ))
            db.update(sql, values)
    return flask.redirect(flask.url_for('user', name=profile_name), 303)

def register_at(app):
    @app.route('/user')
    @app.prpn.requires_auth(2)
    def user_list():
        # For non-Enhanced Users, this redirects to one's own profile page.
        # Eventually, this could display a Friend listing instead.
        user_info = app.prpn.get_user_info()
        if user_info['user_status'] < 3:
            return flask.redirect(flask.url_for('user',
                                                name=user_info['user_name']))
        return handle_user_list(app.prpn.get_database())

    @app.route('/user/<name>', methods=('GET', 'POST'))
    @app.prpn.requires_auth(2)
    def user(name):
        user_info = app.prpn.get_user_info()
        db = app.prpn.get_database()
        if flask.request.method == 'POST':
            result = handle_user_post(name, user_info, db)
            if result is not None:
                return result
        return handle_user_get(name, user_info, db)
