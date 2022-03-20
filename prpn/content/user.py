
import flask

from .. import tmplutil

PAGE_SIZE = 10

VISIBILITY_TO_NAME = {0: 'Private', 1: 'Friends only', 2: 'Public'}

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
    offset = tmplutil.get_request_int64p('offset')
    entries = db.query_many('SELECT name, status, points FROM allUsers '
                                'WHERE status >= 2 '
                                'ORDER BY name ASC LIMIT ? OFFSET ?',
                            (PAGE_SIZE + 1, offset))
    has_more = (len(entries) > PAGE_SIZE)
    entries = entries[:PAGE_SIZE]
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
                                   flask.request.args.get('override')):
        profile_data = {
            'visible': False,
            'visibility': visibility
        }
    else:
        profile_data.update(
            visible=True,
            visibility=visibility,
            visibility_name=VISIBILITY_TO_NAME[visibility]
        )
    display_name = profile_data.get('displayName') or name
    return flask.render_template('content/user.html', profile_name=name,
                                 display_name=display_name,
                                 profile_data=profile_data)

def register_at(app):
    @app.route('/user')
    @app.prpn.requires_auth(2)
    def user_list():
        # For non-Enhanced Users, this redirects to one's own profile page.
        # Eventually, this could displays a Friend listing instead.
        user_info = app.prpn.get_user_info()
        if user_info['user_status'] < 3:
            return flask.redirect(flask.url_for('user',
                                                name=user_info['user_name']))
        return handle_user_list(app.prpn.get_database())

    @app.route('/user/<name>')
    @app.prpn.requires_auth(2)
    def user(name):
        return handle_user_get(name, app.prpn.get_user_info(),
                               app.prpn.get_database())
