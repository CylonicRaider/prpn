#!/usr/bin/env python3
# -*- coding: ascii -*-

import os

import flask

from . import db

app = flask.Flask('prpn')

app.jinja_options = {'trim_blocks': True, 'lstrip_blocks': True}

_database = db.LockedDatabase(os.environ.get('DATABASE',
    os.path.join(app.root_path, '..', 'db.sqlite')))
get_db = _database.register_to(app, flask.g)

@app.route('/')
def index():
    return flask.render_template('index.html')

if __name__ == '__main__': app.run()
