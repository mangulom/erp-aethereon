from datetime import UTC, datetime, timedelta
from functools import lru_cache

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from .config import get_settings


_hasher = PasswordHasher()
ALGORITHM = "HS256"
ISSUER = "aethereon-identity"
AUDIENCE = "aethereon-erp"


def hash_password(plain: str) -> str:
    return _hasher.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _hasher.verify(plain, hashed)
    except VerifyMismatchError:
        return False


def create_access_token(user_id: str, company_ids: list[str], platform_admin: bool) -> tuple[str, str]:
    settings = get_settings()
    now = datetime.now(UTC)
    expires_at = now + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {
        "sub": user_id,
        "exp": expires_at,
        "iat": now,
        "iss": ISSUER,
        "aud": AUDIENCE,
        "platform_admin": platform_admin,
        "companies": company_ids,
        "service": "finance",
    }
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=ALGORITHM, headers={"kid": "aethereon-v1"})
    return token, expires_at.isoformat()


def decode_access_token(token: str) -> dict:
    settings = get_settings()
    return jwt.decode(token, settings.jwt_secret_key, algorithms=[ALGORITHM], issuer=ISSUER, audience=AUDIENCE)
