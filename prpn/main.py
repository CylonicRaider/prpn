#!/usr/bin/env python3
# -*- coding: ascii -*-

import os

import flask

from . import auth, db, forms, schema

app = flask.Flask('prpn')
app.instance_path = os.path.normpath(os.path.join(app.root_path, '..',
                                                  'data'))

try:
    KEY_FILE = os.environ.get('KEY_FILE', os.path.join(app.instance_path,
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
    os.environ.get('DATABASE', os.path.join(app.instance_path, 'db.sqlite')),
    schema.init_schema
)
get_db = _database.register_to(app, flask.g)

_auth_manager = auth.AuthManager(_database, ())

@app.cli.command('init')
def init_files():
    os.makedirs(os.path.normpath(os.path.join(KEY_FILE, '..')), exist_ok=True)
    os.makedirs(os.path.normpath(os.path.join(_database.path, '..')),
                exist_ok=True)
    with open(KEY_FILE, 'ab+') as fp:
        stats = os.fstat(fp.fileno())
        if stats.st_size == 0:
            fp.write(os.urandom(32))
            os.fchmod(fp.fileno(), 0o600)
    print('OK')

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

@app.route('/favicon.ico')
def favicon():
    return flask.send_from_directory(app.static_folder, 'img/favicon.ico')

@app.errorhandler(404)
def error_404(exc):
    return (flask.render_template('404.html'), 404)

if __name__ == '__main__': app.run()
