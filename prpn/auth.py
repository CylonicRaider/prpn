
class AuthProvider:
    def __init__(self, name, display_name):
        self.name = name
        self.display_name = display_name

    def prepare_form(self, form_id):
        raise NotImplementedError

    def register(self, username, form_data):
        raise NotImplementedError

    def login(self, username, form_data):
        raise NotImplementedError

    def logout(self, session_id):
        raise NotImplementedError
