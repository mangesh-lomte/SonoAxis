import os
import secrets
import shutil
import tempfile
import pytest
from fastapi.testclient import TestClient

from backend.app.core.config import settings
from backend.app.db.schema import init_db
from backend.app.main import app
from backend.app.services.auth_service import AuthService


def seed_and_login_test_client(
    tc: TestClient,
    role: str = "Radiologist",
    db_path: str | None = None,
) -> TestClient:
    """Create an isolated runtime test account in target DB and authenticate the client via Bearer + cookie."""
    target_db = db_path or settings.DATABASE_PATH
    suffix = secrets.token_hex(4)
    username = f"pytest_{role.lower()}_{suffix}"
    password = secrets.token_urlsafe(20)
    AuthService.upsert_account_with_password(
        user_id=f"usr-{username}",
        username=username,
        password=password,
        full_name="Dr. Pytest Radiologist" if role == "Radiologist" else "Pytest Administrator",
        role=role,
        designation=role,
        department="Radiology",
        email=f"{username}@sonoaxis.test",
        is_demo=False,
        db_path=target_db,
    )
    res = tc.post("/api/auth/login", json={"username": username, "password": password})
    assert res.status_code == 200, f"Test login failed: {res.status_code} {res.text}"
    payload = res.json()
    tc.headers.update({"Authorization": f"Bearer {payload['access_token']}"})
    if payload.get("csrf_token"):
        tc.headers.update({"X-CSRF-Token": payload["csrf_token"]})
    return tc


@pytest.fixture(scope="session", autouse=True)
def isolated_pytest_database():
    """
    Isolates automated pytest runs from the live production/demo SQLite database
    (D:/sovoice/data/sonovoice.db) so running tests never pollutes demonstration records.
    """
    orig_db_path = settings.DATABASE_PATH
    temp_dir = tempfile.mkdtemp(prefix="sonoaxis_pytest_")
    test_db_path = os.path.join(temp_dir, "pytest_sonovoice.db")

    settings.DATABASE_PATH = test_db_path
    init_db(test_db_path)

    yield test_db_path

    settings.DATABASE_PATH = orig_db_path
    try:
        shutil.rmtree(temp_dir, ignore_errors=True)
    except Exception:
        pass


@pytest.fixture(scope="module")
def client(isolated_pytest_database):
    """Module-scoped TestClient authenticated as an isolated Radiologist user."""
    with TestClient(app) as tc:
        seed_and_login_test_client(tc, role="Radiologist", db_path=isolated_pytest_database)
        yield tc


@pytest.fixture(scope="module")
def admin_client(isolated_pytest_database):
    """Module-scoped TestClient authenticated as an isolated Administrator user."""
    with TestClient(app) as tc:
        seed_and_login_test_client(tc, role="Administrator", db_path=isolated_pytest_database)
        yield tc


@pytest.fixture(scope="function")
def unauth_client(isolated_pytest_database):
    """Fresh unauthenticated TestClient for verifying 401/403 enforcement."""
    with TestClient(app) as tc:
        yield tc
