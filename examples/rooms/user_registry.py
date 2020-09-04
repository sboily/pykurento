from rooms.user_session import UserSession


class UserRegistry:
    def __init__(self):
        self.users_by_name = {}
        self.users_by_session_id = {}

    def register(self, user):
        self.users_by_name[user.get_name()] = user
        self.users_by_session_id[user.get_session()] = user

    def get_by_name(self, name: str) -> UserSession:
        return self.users_by_name.get(name)

    def get_by_session(self, session):
        return self.users_by_session_id.get(session, None)

    def exists(self, name: str) -> bool:
        return name in self.users_by_name

    def remove_by_session(self, session):
        user = self.get_by_session(session)
        try:
            self.users_by_name.__delitem__(user.get_name())
            self.users_by_session_id.__delitem__(session)
        except Exception as ignored:
            pass
        return user
