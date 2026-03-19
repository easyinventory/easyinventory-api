"""
Functional-test fixtures – auth bypass & helpers.

The ``bypass_auth`` fixture replaces ``get_current_user`` with a dependency
that returns a test user from the database (no Cognito token needed).
Every functional test should request this fixture (or use ``autouse``).
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.models.user import User
from testsv2.factories import create_user

# Header that functional tests pass so HTTPBearer doesn't 401.
AUTH_HEADER = {"Authorization": "Bearer fake-test-token"}


@pytest.fixture
async def test_user(db: AsyncSession) -> User:
    """A default authenticated user available in all functional tests."""
    return await create_user(db, email="functest@example.com")


@pytest.fixture
def bypass_auth(app, test_user: User):
    """
    Override ``get_current_user`` so endpoints see ``test_user``
    without touching Cognito at all.
    """

    async def _override():
        return test_user

    app.dependency_overrides[get_current_user] = _override
    try:
        # Tests that depend on this fixture run with the override in place.
        yield
    finally:
        # Ensure the override is removed after each test to avoid leakage.
        app.dependency_overrides.pop(get_current_user, None)
