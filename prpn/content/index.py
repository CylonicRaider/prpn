
import flask

from . import application, lottery

def get_index_info(user_info, db):
    points_row = db.query('SELECT points FROM users WHERE id = ?',
                          (user_info['user_id'],))
    points = None if points_row is None else points_row['points']
    return {'points': points}

def register_at(app):
    @app.route('/')
    def index():
        user_info = app.prpn.get_user_info()
        params = {}
        if user_info['logged_in']:
            if user_info['user_status'] < 2:
                return flask.redirect(flask.url_for('application'))
            db = app.prpn.get_database()
            params.update(get_index_info(user_info, db))
            params.update(application.get_index_info(user_info, db))
            params.update(lottery.get_index_info(user_info, db))
        return flask.render_template('index.html', **params)
