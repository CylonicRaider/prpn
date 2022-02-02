#!/usr/bin/env python3
# -*- coding: ascii -*-

import os

import flask

from . import auth, db, forms, schema

app = flask.Flask('prpn')

DATA_ROOT = os.path.join(app.root_path, '..')

try:
    KEY_FILE = os.environ.get('KEY_FILE', os.path.join(DATA_ROOT,
                                                       'cookie-key.bin'))
    with open(KEY_FILE, 'rb') as fp:
        app.secret_key = fp.read()
except FileNotFoundError:
    app.logger.warn('Secret key file not found!')

app.jinja_options = {'trim_blocks': True, 'lstrip_blocks': True}
app.jinja_env.globals.update(
    get_user_info=auth.get_user_info,
    render_form=forms.render_form
)

_database = db.LockedDatabase(
    os.environ.get('DATABASE', os.path.join(DATA_ROOT, 'db.sqlite')),
    schema.init_schema
)
get_db = _database.register_to(app, flask.g)

_auth_manager = auth.AuthManager(())

@app.cli.command('init-key')
def init_cookie_key():
    with open(KEY_FILE, 'ab+') as fp:
        stats = os.fstat(fp.fileno())
        if stats.st_size != 0:
            print('Key file already exists')
            return
        fp.write(os.urandom(32))
        os.fchmod(fp.fileno(), 0o600)
    print('OK (key file created)')

@app.route('/')
def index():
    return flask.render_template('index.html')

@app.route('/login', methods=('GET', 'POST'))
def login():
    if flask.request.args.get('register'):
        return _auth_manager.handle_register_request()
    else:
        return _auth_manager.handle_login_request()

@app.route('/logout', methods=('GET', 'POST'))
def logout():
    return _auth_manager.handle_logout_request()

if __name__ == '__main__': app.run()
