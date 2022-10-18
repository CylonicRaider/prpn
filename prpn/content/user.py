
import flask

from .. import tmplutil
from . import badges, lottery

PAGE_SIZE = 10

VISIBILITY_DESCS = (
    (2, 'public', 'Public', 'everyone can see your profile'),
    (1, 'friends', 'Friends', 'only your Friends can see your profile'),
    (0, 'private', 'Private', 'only you can see your profile')
)

SUBMIT_DESCS = (
    ('display-name', 'displayName', 64, 'Display name'),
    ('visibility', None, {d[1]: d[0] for d in VISIBILITY_DESCS},
     'Visibility'),
    ('description', None, 4096, 'Description')
)

FRIEND_CHANGE_DESCS = (
    ( 1, 'friend', 'Request Friendship', 'Friend'),
    ( 0, 'neutral', 'Neutral', 'Neutral'),
    (-1, 'block', 'Block', 'Counter-block')
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
    curs.execute('CREATE INDEX IF NOT EXISTS allUsers_name_lower_name ON '
                     'allUsers(LOWER(name), name)')
    curs.execute('CREATE INDEX IF NOT EXISTS allUsers_points ON '
                     'allUsers(points)')

    # FIXME: The bulk queries using friendStatuses and friends (haha) might
    #        need further optimization.
    curs.execute('CREATE TABLE IF NOT EXISTS friendRequests ('
                     'subject INTEGER REFERENCES allUsers ON DELETE CASCADE, '
                     'friend INTEGER REFERENCES allUsers ON DELETE CASCADE, '
                     # -1 = blocked; 0 = neutral (no particular relation);
                     # 1 = Friend.
                     'status INTEGER NOT NULL DEFAULT 0, '
                     'PRIMARY KEY (subject, friend)'
                 ')')
    curs.execute('CREATE INDEX IF NOT EXISTS friendRequests_friend_subject '
                 'ON friendRequests(friend, subject)')
    curs.execute('CREATE VIEW IF NOT EXISTS friendStatuses AS '
                     'SELECT usersSubj.id AS subject, '
                            'usersFriend.id AS friend, '
                            'COALESCE(friendReqsFwd.status, 0) AS fwdStatus, '
                            'COALESCE(friendReqsRev.status, 0) AS revStatus '
                     'FROM users AS usersSubj '
                     'JOIN users AS usersFriend '
                     'LEFT JOIN friendRequests AS friendReqsFwd ON '
                         'friendReqsFwd.subject = usersSubj.id AND '
                         'friendReqsFwd.friend = usersFriend.id '
                     'LEFT JOIN friendRequests AS friendReqsRev ON '
                         'friendReqsRev.subject = usersFriend.id AND '
                         'friendReqsRev.friend = usersSubj.id')
    curs.execute('CREATE VIEW IF NOT EXISTS friendStatuses_fwd AS '
                     'SELECT fwd.subject AS subject, '
                            'fwd.friend AS friend, '
                            'fwd.status AS fwdStatus, '
                            'COALESCE(rev.status, 0) AS revStatus '
                     'FROM friendRequests AS fwd '
                     'LEFT JOIN friendRequests AS rev ON '
                         'rev.subject = fwd.friend AND '
                         'rev.friend = fwd.subject')
    curs.execute('CREATE VIEW IF NOT EXISTS friendStatuses_rev AS '
                     'SELECT rev.friend AS subject, '
                            'rev.subject AS friend, '
                            'COALESCE(fwd.status, 0) AS fwdStatus, '
                            'rev.status AS revStatus '
                     'FROM friendRequests AS rev '
                     'LEFT JOIN friendRequests AS fwd ON '
                         'fwd.subject = rev.friend AND '
                         'fwd.friend = rev.subject')
    curs.execute('CREATE VIEW IF NOT EXISTS friends AS '
                     'SELECT fwd.subject AS subject, '
                            'fwd.friend AS friend, '
                            'fwd.status AS fwdStatus, '
                            'rev.status AS revStatus '
                     'FROM friendRequests AS fwd '
                     'JOIN friendRequests AS rev ON '
                         'rev.subject = fwd.friend AND '
                         'rev.friend = fwd.subject '
                     'WHERE fwd.status > 0 AND rev.status > 0')

def profile_visible(visibility, fwd_rel, rev_rel, profile_owner, viewer_info,
                    allow_override=True):
    # The Friendship relations are "from" the viewer "to" the profile owner.
    if viewer_info['user_id'] == profile_owner or (allow_override and
            viewer_info['user_status'] >= 3):
        # Users may view their own profiles, and Enhanced Users may view all
        # profiles.
        return True
    elif visibility >= 2 and rev_rel >= 0:
        # Public profiles are visible to non-blocked Users.
        return True
    elif visibility >= 1 and fwd_rel > 0 and rev_rel > 0:
        # Friends-only profiles are visible to Friends.
        return True
    else:
        return False

def handle_user_list(db):
    criterion = flask.request.args.get('filter') or 'USER'
    sort = flask.request.args.get('sort') or 'name'
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
    else: # Preferred spelling: ALL
        filter_sql = ''
    if sort == 'id':
        order_sql = 'id ASC'
    elif sort == '-id':
        order_sql = 'id DESC'
    elif sort == 'points':
        order_sql = 'points ASC, id ASC'
    elif sort == '-points':
        order_sql = 'points DESC, id DESC'
    elif sort == '-name':
        order_sql = 'LOWER(name) DESC, name DESC'
    else: # Preferred spelling: name
        order_sql = 'LOWER(name) ASC, name ASC'
    offset = tmplutil.get_request_int64p('offset')

    entries = db.query_many('SELECT id, name, status, points, visibility, '
                                   'displayName, '
                                   'EXISTS(SELECT * FROM allApplications '
                                          'WHERE uid = id) AS hasApplication '
                                'FROM allUsers '
                                'LEFT JOIN userProfiles ON user = id ' +
                                filter_sql +
                                ' ORDER BY ' + order_sql +
                                ' LIMIT ? OFFSET ?',
                            (PAGE_SIZE + 1, offset))
    has_more = (len(entries) > PAGE_SIZE)
    # For visible=True, note that this listing is only accessible to Enhanced
    # Users, which can visit all profile pages anyway.
    entries = [dict(e, visible=True) for e in entries[:PAGE_SIZE]]
    return flask.render_template('content/user-list.html', entries=entries,
        offset=offset, amount=PAGE_SIZE, has_more=has_more)

def handle_friend_list(user_info, db):
    criterion = flask.request.args.get('filter') or 'FRIENDS'
    sort = flask.request.args.get('sort') or 'name'
    if criterion == 'INBOX':
        table_sql = 'friendStatuses_rev'
        filter_sql = 'WHERE fwdStatus = 0 AND revStatus > 0'
    elif criterion == 'OUTBOX':
        table_sql = 'friendStatuses_fwd'
        filter_sql = 'WHERE fwdStatus > 0 AND revStatus <= 0'
    elif criterion == 'BLOCKED':
        table_sql = 'friendStatuses_fwd'
        filter_sql = 'WHERE fwdStatus < 0'
    else: # Preferred spelling: FRIENDS
        table_sql = 'friends'
        filter_sql = ''
    if sort == '-name':
        order_sql = 'LOWER(name) DESC, name DESC'
    else: # Preferred spelling: name
        order_sql = 'LOWER(name) ASC, name ASC'
    offset = tmplutil.get_request_int64p('offset')

    subject, subject_name = user_info['user_id'], user_info['user_name']
    if user_info['user_status'] >= 3 and flask.request.args.get('user'):
        subject_row = db.query('SELECT id, name FROM users WHERE name = ?',
                               (flask.request.args.get('user'),))
        if subject_row:
            subject = subject_row['id']
            subject_name = subject_row['name']

    entries = db.query_many('SELECT id, name, visibility, displayName, '
                                   'fwdStatus, revStatus '
                                'FROM ' + table_sql +
                                ' JOIN users ON subject = ? AND friend = id '
                                'LEFT JOIN userProfiles ON user = id ' +
                                filter_sql +
                                ' ORDER BY ' + order_sql +
                                ' LIMIT ? OFFSET ?',
                            (subject, PAGE_SIZE + 1, offset))
    has_more = (len(entries) > PAGE_SIZE)
    entries = [dict(e, visible=profile_visible(e['visibility'] or 0,
                                               e['fwdStatus'], e['revStatus'],
                                               e['id'], user_info))
               for e in entries[:PAGE_SIZE]]
    counts = get_friend_request_counts({'user_id': subject}, db)
    return flask.render_template('content/user-list.html', friend_mode=True,
         subject_id=subject, subject_name=subject_name,
         entries=entries, offset=offset, amount=PAGE_SIZE, has_more=has_more,
         request_counts=counts)

def handle_user_get(name, acc_info, db):
    profile_row = db.query('SELECT allUsers.*, userProfiles.*, '
                                  'EXISTS(SELECT * FROM allApplications '
                                         'WHERE uid = id) AS hasApplication, '
                                  'friendStatuses.fwdStatus AS friendFwd, '
                                  'friendStatuses.revStatus AS friendRev '
                               'FROM allUsers '
                               'LEFT JOIN userProfiles ON id = user '
                               'JOIN friendStatuses ON subject = ? AND '
                                                      'friend = id '
                               'WHERE status >= 2 AND name = ?',
                           (acc_info['user_id'], name))
    if profile_row is None:
        profile_data = {'id': None, 'visibility': -1}
    else:
        profile_data = dict(profile_row)
        profile_data.pop('user', None)

    visibility = profile_data['visibility'] or 0
    really_visible = False
    if profile_row is not None:
        really_visible = profile_visible(
            visibility,
            profile_data.get('friendFwd', 0),
            profile_data.get('friendRev', 0),
            profile_data['id'],
            acc_info,
            bool(flask.request.args.get('force'))
        )

    if really_visible:
        profile_data.update(
            visible=True,
            badges=badges.get_user_badges(db, profile_data['id'])
        )
    else:
        profile_data = {'visible': False}
    profile_data['visibility'] = visibility
    if not profile_data.get('displayName'):
        profile_data['displayName'] = name
    if not profile_data.get('friendFwd'):
        profile_data['friendFwd'] = 0
    if not profile_data.get('friendRev'):
        profile_data['friendRev'] = 0

    if profile_data['visible'] and acc_info['user_status'] >= 3:
        profile_data.update(
            has_extra=True,
            lottery_extra=lottery.get_profile_info(profile_data['id'], db)
        )

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
            raise AssertionError('Invalid user editor field description?!')
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
            db.insert(sql, values)
    return flask.redirect(flask.url_for('user', name=profile_name), 303)

def handle_friend_change(user_info, db):
    other_name = flask.request.args.get('name')

    user_exists, user_visible = False, False
    fwd_status, rev_status = None, None
    if other_name:
        entry = db.query('SELECT friend, visibility, fwdStatus, revStatus '
                             'FROM friendStatuses '
                             'JOIN users ON friend = id '
                             'LEFT JOIN userProfiles ON user = friend '
                             'WHERE subject = ? AND name = ?',
                         (user_info['user_id'], other_name))
        if entry:
            user_exists = True
            fwd_status = entry['fwdStatus']
            rev_status = entry['revStatus']
            user_visible = profile_visible(
                entry['visibility'] or 0,
                fwd_status,
                rev_status,
                entry['friend'],
                user_info
            )

            if entry['friend'] == user_info['user_id']:
                flask.flash('Cannot befriend or block yourself', 'error')
                return flask.redirect(flask.url_for('friend_change',
                    action=flask.request.args.get('action')), 302)

    return flask.render_template('content/friend-change.html',
        user_exists=user_exists, user_visible=user_visible,
        fwd_status=fwd_status, rev_status=rev_status,
        all_changes=FRIEND_CHANGE_DESCS)

def handle_friend_change_post(user_info, db):
    other_name = flask.request.form.get('name')
    if not other_name:
        return flask.abort(400)

    action = flask.request.form.get('action')
    if not action:
        flask.flash('New Friendship status was not selected', 'error')
        if 'name' not in flask.request.args:
            return flask.redirect(flask.url_for('friend_change',
                                                name=other_name),
                                  303)
        return None
    try:
        new_status = {'friend': 1, 'neutral': 0, 'block': -1}[action]
    except KeyError:
        return flask.abort(400)

    with db.transaction(True):
        # Resolve the other user.
        other_row = db.query('SELECT id FROM users WHERE name = ?',
                             (other_name,))
        if not other_row:
            flask.flask('No such user', 'error')
            return None
        other_id = other_row['id']

        # Avoid introducing hard-to-interpret state.
        if other_id == user_info['user_id']:
            flask.flash('Cannot befriend or block yourself', 'error')
            return None

        # Retrieve the pre-update status (for more expressive flashing).
        old_row = db.query('SELECT status FROM friendRequests '
                               'WHERE subject = ? AND friend = ?',
                           (user_info['user_id'], other_id))
        old_status = old_row['status'] if old_row else 0

        # If other has blocked us, create no false hopes.
        reverse_row = db.query('SELECT status FROM friendRequests '
                                   'WHERE subject = ? AND friend = ?',
                               (other_id, user_info['user_id']))
        if reverse_row and reverse_row['status'] < 0 and new_status > 0:
            flask.flash('User {} has blocked you'.format(other_name), 'error')
            return None
        reverse_status = reverse_row['status'] if reverse_row else 0

        # Perform the status change.
        if new_status == 0:
            db.update('DELETE FROM friendRequests '
                          'WHERE subject = ? AND friend = ?',
                      (user_info['user_id'], other_id))
        else:
            updated = db.update('UPDATE friendRequests SET status = ? '
                                    'WHERE subject = ? AND friend = ?',
                                (new_status, user_info['user_id'], other_id))
            if not updated:
                db.insert('INSERT INTO friendRequests(subject, friend, '
                                                     'status) '
                              'VALUES (?, ?, ?)',
                          (user_info['user_id'], other_id, new_status))

        # Formulate an appropriate response.
        msg, cat = None, 'info'
        if new_status > 0:
            if reverse_status > 0:
                if old_status > 0:
                    msg = 'User {} and you are Friends!'
                else:
                    msg = 'User {} and you are Friends now!'
                cat = 'success'
            else:
                if old_status > 0:
                    msg = 'Friend request already sent'
                else:
                    msg = 'Friend request sent...'
        elif new_status == 0:
            if old_status > 0:
                msg = 'Friendship withdrawn'
            elif old_status < 0:
                msg = 'Block withdrawn'
            else:
                msg = 'Social relationship to User {} remains neutral'
        else:
            msg = 'User {} '
            if old_status < 0:
                msg += 'already '
            if reverse_status < 0:
                msg += 'mutually '
            msg += 'blocked'
        flask.flash(msg.format(other_name), cat)

        # Done.
        return flask.redirect(flask.url_for('friend_change', name=other_name),
                              303)

def get_friend_request_counts(user_info, db):
    def len_to_str(rows):
        return tmplutil.len_to_str(len(rows))

    inbox = len_to_str(db.query_many(
        'SELECT 1 FROM friendStatuses_rev '
        'WHERE subject = ? AND fwdStatus = 0 AND revStatus > 0 '
        'LIMIT 11',
        (user_info['user_id'],)
    ))
    outbox = len_to_str(db.query_many(
        'SELECT 1 FROM friendStatuses_fwd '
        'WHERE subject = ? AND fwdStatus > 0 AND revStatus <= 0 '
        'LIMIT 11',
        (user_info['user_id'],)
    ))

    return {'inbox': inbox, 'outbox': outbox}

def get_index_info(user_info, db):
    profile_row = db.query('SELECT displayName FROM userProfiles '
                               'WHERE user = ?',
                           (user_info['user_id'],))
    display_name = None if profile_row is None else profile_row['displayName']

    return {'display_name': display_name,
            'friend_counts': get_friend_request_counts(user_info, db)}

def register_at(app):
    @app.route('/user')
    @app.prpn.requires_auth(2)
    def user_list():
        # User listing is not available to non-Enhanced Users; they get
        # redirected to the closest service available, viz. the Friends
        # listing.
        user_info = app.prpn.get_user_info()
        if user_info['user_status'] < 3 or flask.request.args.get('friends'):
            return flask.redirect(flask.url_for('friend_list'))
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

    @app.route('/friend')
    @app.prpn.requires_auth(2)
    def friend_list():
        return handle_friend_list(app.prpn.get_user_info(),
                                  app.prpn.get_database())

    @app.route('/friend/change', methods=('GET', 'POST'))
    @app.prpn.requires_auth(2)
    def friend_change():
        user_info = app.prpn.get_user_info()
        db = app.prpn.get_database()
        if flask.request.method == 'POST':
            result = handle_friend_change_post(user_info, db)
            if result is not None:
                return result
        return handle_friend_change(user_info, db)
