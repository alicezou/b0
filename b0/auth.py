import os

class AuthManager:
    def __init__(self, workspace: str):
        self.workspace = workspace
        self.auth_path = os.path.join(workspace, "authorized_users")
        self.tokens_path = os.path.join(workspace, "tokens")
        
        self.users = self._load_users()
        self.admin_tokens = []
        self.user_tokens = []
        self._load_tokens()

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
            return
        
        self.admin_tokens = []
        self.user_tokens = []
        
        with open(self.tokens_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line == ".":
                    continue
                parts = line.split()
                if len(parts) == 2:
                    t, role = parts[0], parts[1]
                    if role == "admin":
                        self.admin_tokens.append(t)
                    else:
                        self.user_tokens.append(t)
                else:
                    # Fallback for old simple format (treat as user)
                    self.user_tokens.append(parts[0])

    def _save_users(self):
        os.makedirs(self.workspace, exist_ok=True)
        with open(self.auth_path, "w") as f:
            for uid, priv in self.users.items():
                f.write(f"{uid} {priv}\n")

    def _save_tokens(self):
        os.makedirs(self.workspace, exist_ok=True)
        with open(self.tokens_path, "w") as f:
            for token in self.admin_tokens:
                f.write(f"{token} admin\n")
            for token in self.user_tokens:
                f.write(f"{token} user\n")

    def is_authorized(self, uid: int) -> bool:
        return uid in self.users

    def validate_token(self, token: str) -> bool:
        return token in self.admin_tokens or token in self.user_tokens

    def authorize(self, uid: int, token: str) -> str | None:
        if self.is_authorized(uid):
            return self.users[uid]

        priv = None
        if token in self.admin_tokens:
            self.admin_tokens.remove(token)
            priv = "admin"
        elif token in self.user_tokens:
            self.user_tokens.remove(token)
            priv = "user"
        
        if priv:
            self._save_tokens()
            self.users[uid] = priv
            self._save_users()
            return priv
        
        return None

    @property
    def tokens(self) -> list[str]:
        return self.admin_tokens + self.user_tokens

    def get_privilege(self, uid: int) -> str:
        return self.users.get(uid)
