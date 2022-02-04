
import os
import base64
import sqlite3
import urllib.parse

from flask import flash, render_template, request, session
from markupsafe import Markup

from . import forms

GENERIC_LOGOUT_FORM = (
    (None, 'label', 'Are you sure you want to log out?'),
    (None, 'submit', 'Log out')
)

STATUS_TO_NAME = {0: 'Non-User', 1: 'Potential User Entity', 2: 'User',
                  3: 'Enhanced User'}

class AuthProvider:
    def __init__(self, name, display_name):
        self.name = name
        self.display_name = display_name

    def prepare_form(self, form_id):
        if form_id == 'logout':
            return (200, '', GENERIC_LOGOUT_FORM)
        elif form_id in ('register', 'login'):
            # These should actually be implemented by subclasses.
            raise NotImplementedError
        else:
            raise RuntimeError('Unrecognized auth form {}'.format(form_id))

    def register(self, session_id, form_data):
        raise NotImplementedError

    def login(self, session_id, form_data):
        raise NotImplementedError

    def logout(self, session_id):
        raise NotImplementedError

def get_user_info():
    try:
        return {'logged_in': True,
                'session_id': session['sid'],
                'user_id': session['uid'],
                'user_name': session['name'],
                'user_status': session['status'],
                'user_type': STATUS_TO_NAME[session['status']]}
    except KeyError:
        return {'logged_in': False}

def sanitize_next_url(text):
    if not text: return '/'
    components = urllib.parse.urlsplit(text)
    if components.scheme or components.netloc: return '/'
    return text

class AuthManager:
    def __init__(self, db, providers):
        self.db = db
        self.providers = providers
        self._provider_map = {p.name: p for p in providers}

    def do_register(self, info):
        try:
            with self.db as db:
                uid = db.update('INSERT INTO allUsers (name, status) '
                                'VALUES (?, ?)',
                                (info['name'], 1))
                return {'uid': uid, 'status': 1}
        except sqlite3.IntegrityError:
            return None

    def do_login(self, info):
        with self.db as db:
            result = db.query('SELECT id, status FROM allUsers '
                              'WHERE name = ?',
                              (info['name'],))
            if result is None: return None
            return {'uid': result['id'], 'status': result['status']}

    def _finish_post(self, reqname, user_details):
        if reqname == 'register':
            return self.do_register(user_details)
        elif reqname == 'login':
            return self.do_login(user_details)
        else:
            raise RuntimeError('Unrecognized request type {}'.format(reqname))

    def _get_session_id(self):
        raw_token = base64.b64encode(os.urandom(32))
        return raw_token.decode('ascii').replace('=', '')

    def _clear_session(self):
        for key in ('sid', 'provider', 'uid', 'name', 'status'):
            session.pop(key, None)

    def _get_next_url(self):
        return sanitize_next_url(request.args.get('continue'))

    def _handle_generic_request(self, reqname, heading, post_cb):
        result, run_provider = None, None
        if request.method == 'POST':
            provider = self._provider_map[request.form['provider']]
            sid = self._get_session_id()
            p_result = post_cb(provider, sid, request.form)
            if p_result:
                details = self._finish_post(reqname, p_result)
                if details is not None:
                    session['sid'] = sid
                    session['provider'] = provider.name
                    session['uid'] = details['uid']
                    session['name'] = p_result['name']
                    session['status'] = details['status']
                    result = (302, self._get_next_url())
                else:
                    self._clear_session()
                    flash('Invalid credentials', 'error')
            else:
                self._clear_session()
                flash('Invalid credentials', 'error')
        if result is not None:
            # If the operation did not fail, we do not replace its result.
            pass
        elif len(self.providers) == 0:
            result = (200, Markup('<p><i>Account functionality is not '
                                  'enabled.</i></p>'))
        elif len(self.providers) == 1:
            run_provider = self.providers[0]
        else:
            provider_name = request.args.get('provider')
            run_provider = self._provider_map.get(provider_name)
            if run_provider is None:
                result = (200, '', [(None, 'label', 'Proceed using:')] +
                        [(k, 'hidden', None, v)
                         for k, v in request.args.items()
                         if k != 'provider'] +
                        [('provider', 'submit', p.display_name, p.name)
                         for p in self.providers],
                    'get')
        if run_provider is not None:
            result = run_provider.prepare_form(reqname)
            if 200 <= result[0] < 300:
                result = (result[0], result[1],
                    [('provider', 'hidden', None, run_provider.name)] +
                        list(result[2]),
                    *result[3:])
        return forms.execute_form_or_redirect(result, 'form.html',
                                              heading=heading)

    def _handle_redundant_request(self, heading, text):
        form_content = (Markup('<p>%s</p>\n'
            '<p><a href="%s" class="btn btn-primary">Continue</a></p>') %
            (text, self._get_next_url()))
        return render_template('form.html', heading=heading,
                               form_content=form_content)

    def handle_register_request(self):
        if get_user_info()['logged_in']:
            return self._handle_redundant_request('Already logged in',
                'You already are logged in.')
        return self._handle_generic_request('register', 'Sign up',
            lambda provider, sid, data: provider.register(sid, data))

    def handle_login_request(self):
        if get_user_info()['logged_in']:
            return self._handle_redundant_request('Already logged in',
                'You already are logged in.')
        return self._handle_generic_request('login', 'Log in',
            lambda provider, sid, data: provider.login(sid, data))

    def handle_logout_request(self):
        if not get_user_info()['logged_in']:
            return self._handle_redundant_request('Already logged out',
                                                  'You are not logged in.')
        elif request.method == 'POST':
            next_url = sanitize_next_url(request.args.get('continue'))
            try:
                provider = self._provider_map.get(session.get('provider'))
                sid = session.get('sid')
                if provider and sid:
                    provider.logout(sid)
            finally:
                self._clear_session()
            result = (302, next_url)
        else:
            provider = self._provider_map.get(session.get('provider'))
            if provider:
                result = provider.prepare_form('logout')
            else:
                result = (200, '', GENERIC_LOGOUT_FORM)
        return forms.execute_form_or_redirect(result, 'form.html',
                                              heading='Log out')

    def register_routes(self, app):
        @app.route('/login', methods=('GET', 'POST'))
        def login():
            if request.args.get('register'):
                return self.handle_register_request()
            else:
                return self.handle_login_request()

        @app.route('/logout', methods=('GET', 'POST'))
        def logout():
            return self.handle_logout_request()
