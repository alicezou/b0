import os

class AuthManager:
    def __init__(self, workspace: str):
        self.workspace = workspace
        self.path = os.path.join(workspace, "authorized_users")
        self.users = self._load()

    def _load(self):
        users = {}
        if os.path.exists(self.path):
            with open(self.path, "r") as f:
                for line in f:
                    p = line.split()
                    if len(p) >= 2: users[int(p[0])] = p[1]
        return users

    def _save(self):
        os.makedirs(self.workspace, exist_ok=True)
        with open(self.path, "w") as f:
            for uid, priv in self.users.items():
                f.write(f"{uid} {priv}\n")

    def is_authorized(self, uid: int) -> bool:
        return uid in self.users

    def authorize(self, uid: int) -> str:
        if uid not in self.users:
            self.users[uid] = "admin" if not self.users else "user"
            self._save()
        return self.users[uid]

    def get_privilege(self, uid: int) -> str:
        return self.users.get(uid)
