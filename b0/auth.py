import os

class AuthManager:
    def __init__(self, workspace: str):
        self.workspace = workspace
        self.auth_path = os.path.join(workspace, "authorized_users")
        self.tokens_path = os.path.join(workspace, "tokens")
        
        self.users = self._load_users()
        self.tokens = self._load_tokens()

    def _load_users(self):
        users = {}
        if os.path.exists(self.auth_path):
            with open(self.auth_path, "r") as f:
                for line in f:
                    p = line.split()
                    if len(p) >= 2: users[int(p[0])] = p[1]
        return users

    def _load_tokens(self):
        if not os.path.exists(self.tokens_path):
            return []
        
        with open(self.tokens_path, "r") as f:
            return [line.strip() for line in f if line.strip()]

    def _save_users(self):
        os.makedirs(self.workspace, exist_ok=True)
        with open(self.auth_path, "w") as f:
            for uid, priv in self.users.items():
                f.write(f"{uid} {priv}\n")

    def _save_tokens(self):
        os.makedirs(self.workspace, exist_ok=True)
        with open(self.tokens_path, "w") as f:
            for token in self.tokens:
                f.write(f"{token}\n")

    def is_authorized(self, uid: int) -> bool:
        return uid in self.users

    def validate_token(self, token: str) -> bool:
        return token in self.tokens

    def authorize(self, uid: int, token: str) -> str | None:
        if self.is_authorized(uid):
            return self.users[uid]

        if token in self.tokens:
            self.tokens.remove(token)
            self._save_tokens()
            
            priv = "admin" if not self.users else "user"
            self.users[uid] = priv
            self._save_users()
            return priv
        
        return None

    def get_privilege(self, uid: int) -> str:
        return self.users.get(uid)
