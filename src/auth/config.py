import os
from dataclasses import dataclass
from typing import Optional, Set


@dataclass
class AuthConfig:
    auth_db_path: str
    admin_tokens: Set[str]


_config: Optional[AuthConfig] = None


def configure_auth(config: AuthConfig) -> None:
    global _config
    _config = config


def get_auth_config() -> AuthConfig:
    if _config is None:
        raise RuntimeError("Auth configuration has not been initialized")
    return _config


def get_admin_tokens() -> Set[str]:
    return get_auth_config().admin_tokens


def build_auth_config_from_env() -> AuthConfig:
    return AuthConfig(
        auth_db_path=os.getenv("AUTH_DB_PATH", "db/auth.sqlite3"),
        admin_tokens={
            token.strip()
            for token in os.getenv("ADMIN_API_TOKENS", "").split(",")
            if token.strip()
        },
    )
