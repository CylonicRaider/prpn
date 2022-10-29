
from prpn.auth import AuthProvider

class TestAuthProvider(AuthProvider):
    def __init__(self):
        super().__init__('test', 'Testing')

    def prepare_form(self, form_id):
        if form_id not in ('register', 'login'):
            return super().prepare_form(form_id)
        return (200, '', (
            ('name', 'text', 'User name:', None, 'user-name'),
            (None, 'submit', 'Submit')
        ))

    def register(self, session_id, form_data):
        # Registering test users always works.
        return {'name': form_data['name']}

    def login(self, session_id, form_data):
        # Logging in always works, too.
        return {'name': form_data['name']}

    def logout(self, session_id):
        pass

PROVIDER = TestAuthProvider()
