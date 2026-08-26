import hashlib


def hash_token(token: str) -> str:
    """Return the SHA-256 hexadecimal digest for a bearer token."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def token_fingerprint(token_hash: str) -> str:
    """Return a short, non-secret identifier derived from a token hash."""
    if len(token_hash) <= 8:
        return token_hash[:2] + "***"
    return token_hash[:4] + "..." + token_hash[-4:]
