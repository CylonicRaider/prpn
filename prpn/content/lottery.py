
import flask

def init_schema(curs):
    curs.execute('CREATE TABLE IF NOT EXISTS lottery ('
                     'user INTEGER PRIMARY KEY REFERENCES users '
                         'ON DELETE CASCADE, '
                     'awarded INTEGER NOT NULL, '
                     'totalAwarded INTEGER NOT NULL'
                 ')')

def handle_get(user_info, lot_data):
    enrolled = (lot_data is not None)
    awarded = lot_data['awarded'] if enrolled else 0
    total_awarded = lot_data['totalAwarded'] if enrolled else 0
    return flask.render_template('content/lottery.html',
        enrolled=enrolled, awarded=awarded, total_awarded=total_awarded)

def register_at(app):
    @app.route('/lottery')
    @app.prpn.requires_auth(0)
    def lottery():
        user_info = app.prpn.get_user_info()
        lot_data = app.prpn.get_database().query('SELECT * FROM lottery '
                                                     'WHERE user = ?',
                                                 (user_info['user_id'],))
        return handle_get(user_info, lot_data)
