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
                    if len(p) >= 3:
                        users[int(p[0])] = {"priv": p[1], "token": p[2], "username": p[3] if len(p) > 3 else "unknown"}
                    elif len(p) == 2:
                        users[int(p[0])] = {"priv": p[1], "token": "legacy", "username": "legacy"}
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
            for uid, info in self.users.items():
                f.write(f"{uid} {info['priv']} {info['token']} {info['username']}\n")

    def _save_tokens(self):
        os.makedirs(self.workspace, exist_ok=True)
        with open(self.tokens_path, "w") as f:
            for token in self.admin_tokens:
                f.write(f"{token} admin\n")
            for token in self.user_tokens:
                f.write(f"{token} user\n")

    def is_authorized(self, uid: int) -> bool:
        return uid in self.users

    def authorize(self, uid: int, token: str, username: str = "unknown") -> str | None:
        if self.is_authorized(uid):
            return self.users[uid]["priv"]

        priv = None
        if token in self.admin_tokens:
            self.admin_tokens.remove(token)
            priv = "admin"
        elif token in self.user_tokens:
            self.user_tokens.remove(token)
            priv = "user"
        
        if priv:
            self._save_tokens()
            self.users[uid] = {"priv": priv, "token": token, "username": username}
            self._save_users()
            return priv
        
        return None

    def get_identifier(self, uid: int) -> str:
        info = self.users.get(uid)
        if not info: return str(uid)
        # Use first 8 chars of token for brevity but still unique
        t_short = info["token"][:8] if info["token"] != "legacy" else "legacy"
        username = info["username"] or "unknown"
        return f"{username}-{t_short}"

    @property
    def tokens(self) -> list[str]:
        return self.admin_tokens + self.user_tokens

    def get_privilege(self, uid: int) -> str | None:
        info = self.users.get(uid)
        if isinstance(info, dict):
            return info["priv"]
        return info # Legacy case
