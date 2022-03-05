#!/usr/bin/env python3
# -*- coding: ascii -*-

import os

import click
import flask

from . import auth, db, scheduler, schema, tmplutil
from .content import application, transfer, complaint

app = flask.Flask('prpn')
app.instance_path = os.environ.get('DATA_DIR',
    os.path.normpath(os.path.join(app.root_path, '..', 'data')))
app.prpn = flask.ctx._AppCtxGlobals()

_init_tasks = []
def run_init_tasks():
    tasks, _init_tasks[:] = _init_tasks[:], []
    for task in tasks:
        task()
app.prpn.run_init_tasks = run_init_tasks
app.prpn.init_task = _init_tasks.append

KEY_FILE = os.path.join(app.instance_path, 'cookie-key.bin')
@app.prpn.init_task
def load_key_file():
    try:
        with open(KEY_FILE, 'rb') as fp:
            app.secret_key = fp.read()
    except FileNotFoundError:
        app.logger.warn('Secret key file not found!')

app.jinja_options = {'trim_blocks': True, 'lstrip_blocks': True}
app.jinja_env.globals.update(
    min=min,
    max=max,
    add_query=tmplutil.add_query,
    render_timestamp=tmplutil.render_timestamp,
    render_form=tmplutil.render_form
)

_database = db.LockedDatabase(os.path.join(app.instance_path, 'db.sqlite'),
                              schema.init_schema)
app.prpn.get_database = _database.register_to(app, flask.g)

_scheduler = scheduler.Scheduler(_database, app.logger)
app.prpn.schedule_cb_ex = _scheduler.add_callback_ex
app.prpn.schedule_cb = _scheduler.add_callback
app.prpn.schedule_regular = _scheduler.add_regular
app.prpn.schedule = _scheduler.schedule_later

_auth_providers = auth.providers_from_name(os.environ.get('AUTH_PROVIDER'))
for _provider in _auth_providers: _provider.register_at(app)
_auth_manager = auth.AuthManager(_database, _auth_providers)

app.jinja_env.globals['get_user_info'] = _auth_manager.get_user_info
app.prpn.get_user_info = _auth_manager.get_user_info
app.prpn.reload_user_info = _auth_manager.reload_user_info
app.prpn.requires_auth = auth.requires_auth

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

@app.cli.command('add-points',
                 help='Add (positive or negative) printing points to the '
                      'given account\'s balance')
@click.argument('name')
@click.argument('points', type=int)
def add_points(name, points):
    with _database as db:
        count = db.update('UPDATE allUsers SET points = points + ? '
                              'WHERE name = ?',
                          (points, name))
        if not count:
            raise ValueError('Unrecognized user {!r}'.format(name))
    print('OK')

@app.route('/')
def index():
    user_info = app.prpn.get_user_info()
    points, has_app, app_counts = None, None, None
    if user_info['logged_in']:
        if user_info['user_status'] < 2:
            return flask.redirect(flask.url_for('application'))
        db = app.prpn.get_database()
        row = db.query('SELECT points FROM users WHERE id = ?',
                       (user_info['user_id'],))
        if row is not None:
            points = row['points']
        has_app = db.query('SELECT 1 FROM applications WHERE user = ?',
                           (user_info['user_id'],))
        if user_info['user_status'] >= 3:
            app_counts = application.get_application_counts(db)
    return flask.render_template('index.html', points=points,
        has_application=has_app, app_counts=app_counts)

@app.route('/favicon.ico')
def favicon():
    return flask.send_from_directory(app.static_folder, 'img/favicon.ico')

@app.errorhandler(404)
def error_404(exc):
    return (flask.render_template('404.html'), 404)

_auth_manager.register_at(app)
_scheduler.register_at(app)
application.register_at(app)
transfer.register_at(app)
complaint.register_at(app)

if __name__ == '__main__':
    run_init_tasks()
    app.run()
elif (os.environ.get('FLASK_RUN_FROM_CLI') == 'true' and
        os.environ.get('FORCE_INIT') != 'true'):
    # HACK: Flask does not provide a clear indication of whether the server
    #       is going to be run, so we guess "yes" whenever the current command
    #       is some sort of "run".
    _ctx = click.get_current_context()
    if _ctx and _ctx.info_name == 'run':
        run_init_tasks()
else:
    run_init_tasks()
