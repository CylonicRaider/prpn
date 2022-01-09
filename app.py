#!/usr/bin/env python3
# -*- coding: ascii -*-

from flask import Flask

app = Flask('prpn')

@app.route('/')
def handle_root():
    return ('Hello World!', {'Content-Type': 'text/plain; charset=utf-8'})

if __name__ == '__main__': app.run()
