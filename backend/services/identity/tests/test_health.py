import os
from uuid import uuid4

os.environ.setdefault("JWT_SECRET_KEY", "test-only-secret-never-used-outside-unit-tests-000000")

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app, login  # noqa: E402
from app.schemas import LoginRequest  # noqa: E402
from app.security import create_access_token, hash_password  # noqa: E402


def test_live_endpoint_reports_the_service() -> None:
    with TestClient(app) as client:
        response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json()["service"] == "identity"
    assert response.headers["cache-control"] == "no-store"


def test_login_uses_argon2_and_returns_a_scoped_token(monkeypatch) -> None:
    class FakeResult:
        def __init__(self, record=None, rows=None):
            self.record = record
            self.rows = rows or []

        def mappings(self):
            return self

        def first(self):
            return self.record

        def all(self):
            return self.rows

        def scalar_one(self):
            return self.record

    class FakeDb:
        def __init__(self):
            self.commits = 0
            self.queries = []

        def execute(self, statement, params=None):
            sql = str(statement)
            self.queries.append(sql)
            normalized = " ".join(sql.split())
            if "FROM users WHERE lower(email)" in normalized:
                return FakeResult({
                    "id": user_id,
                    "email": "operator@example.com",
                    "display_name": "Platform Operator",
                    "password_hash": password_hash,
                    "is_active": True,
                    "is_platform_admin": False,
                    "locked_until": None,
                })
            if "FROM memberships m" in normalized and "JOIN roles r" in normalized:
                return FakeResult(rows=[(company_id,)])
            return FakeResult()

        def commit(self):
            self.commits += 1

    user_id, company_id = uuid4(), uuid4()
    password_hash = hash_password("Safe-Test-Password-2026!")
    fake_db = FakeDb()
    response = login(
        LoginRequest(email="operator@example.com", password="Safe-Test-Password-2026!"),
        fake_db,
    )
    assert response.user.id == user_id
    assert response.user.email == "operator@example.com"
    assert response.access_token
    assert fake_db.commits == 1
    assert any("identity.login.succeeded" in sql for sql in fake_db.queries)
