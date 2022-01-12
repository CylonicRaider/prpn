#!/usr/bin/env python3
# -*- coding: ascii -*-

import os

import flask

from . import db

app = flask.Flask('prpn')

_database = db.LockedDatabase(os.environ.get('DATABASE',
    os.path.join(app.root_path, '..', 'db.sqlite')))
get_db = _database.register_to(app, flask.g)

@app.route('/')
def handle_root():
    return ('Hello World!', {'Content-Type': 'text/plain; charset=utf-8'})

if __name__ == '__main__': app.run()
