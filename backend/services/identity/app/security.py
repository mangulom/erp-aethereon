from datetime import UTC, datetime, timedelta
from functools import lru_cache

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from .config import get_settings


_hasher = PasswordHasher()
ALGORITHM = "HS256"
ISSUER = "aethereon-identity"
AUDIENCE = "aethereon-erp"


def hash_password(plain: str) -> str:
    return _hasher.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _hasher.verify(hashed, plain)
    except (VerificationError, InvalidHashError):
        return False


def create_access_token(user_id: str, company_ids: list[str], platform_admin: bool, permissions: list[str] | None = None) -> tuple[str, datetime]:
    settings = get_settings()
    now = datetime.now(UTC)
    expires_at = now + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {
        "sub": str(user_id),
        "exp": expires_at,
        "iat": now,
        "iss": ISSUER,
        "aud": AUDIENCE,
        "platform_admin": platform_admin,
        "companies": [str(company_id) for company_id in company_ids],
        "permissions": sorted(set(permissions or [])),
        "service": "finance",
    }
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=ALGORITHM, headers={"kid": "aethereon-v1"})
    return token, expires_at


def decode_access_token(token: str) -> dict:
    settings = get_settings()
    return jwt.decode(token, settings.jwt_secret_key, algorithms=[ALGORITHM], issuer=ISSUER, audience=AUDIENCE)
