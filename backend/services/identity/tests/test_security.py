import os

os.environ.setdefault("JWT_SECRET_KEY", "test-only-secret-never-used-outside-unit-tests-000000")

from uuid import uuid4

from app.security import create_access_token, hash_password, verify_password
from app.schemas import LoginRequest
import jwt
from app.config import get_settings


def test_password_hash_verifies_only_the_matching_password() -> None:
    encoded = hash_password("Correct-Horse-42")
    assert encoded.startswith("$argon2id$")
    assert verify_password("Correct-Horse-42", encoded)
    assert not verify_password("incorrect", encoded)


def test_password_verification_rejects_malformed_hash_without_crashing() -> None:
    assert not verify_password("any-password", "not-an-argon2-hash")
    assert not verify_password("wrong-password", hash_password("correct-password"))


def test_access_token_includes_only_the_authorized_company_memberships() -> None:
    user_id, company_id = uuid4(), uuid4()
    token, expiry = create_access_token(user_id, [company_id], False)
    assert token
    assert expiry.tzinfo is not None
    claims = jwt.decode(token, get_settings().jwt_secret_key, algorithms=["HS256"], audience="aethereon-erp", issuer="aethereon-identity")
    assert claims["sub"] == str(user_id)
    assert claims["companies"] == [str(company_id)]


def test_identity_local_port_is_configurable(monkeypatch) -> None:
    monkeypatch.setenv("IDENTITY_PORT", "10009")
    assert get_settings().configured_port == 10009


def test_login_request_rejects_malformed_email() -> None:
    try:
        LoginRequest(email="not-an-email", password="some-long-password")
    except Exception as exc:
        assert exc.__class__.__name__ == "ValidationError"
    else:
        raise AssertionError("A malformed email was accepted.")
