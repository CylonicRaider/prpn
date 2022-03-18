
import flask

from . import application

def register_at(app):
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
