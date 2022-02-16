
import flask

COMPLAINT_CALLBACK = None

def handle_complaint(user_info, text):
    if COMPLAINT_CALLBACK is not None:
        return COMPLAINT_CALLBACK(user_info, text)

def register_at(app):
    @app.route('/security/complain', methods=('GET', 'POST'))
    @app.prpn.requires_auth(2)
    def acs_complaint():
        user_info = app.prpn.get_user_info()
        if flask.request.method == 'POST':
            result = handle_complaint(user_info, flask.request.form['text'])
            if result is not None: return result
            return flask.redirect(flask.url_for('acs_complaint'), 303)
        return flask.render_template('content/complain.html')
