import os
from unittest.mock import patch

from app.core.config import Settings


def test_database_url_is_configurable():
    s = Settings(
        DATABASE_URL="postgresql+asyncpg://test:test@localhost/testdb",
        COGNITO_REGION="",
        COGNITO_USER_POOL_ID="",
        COGNITO_APP_CLIENT_ID="",
        BOOTSTRAP_ADMIN_EMAIL="",
    )
    assert "testdb" in s.DATABASE_URL


@patch.dict(os.environ, {"DATABASE_URL": ""}, clear=False)
def test_database_url_default_is_empty():
    s = Settings(
        COGNITO_REGION="",
        COGNITO_USER_POOL_ID="",
        COGNITO_APP_CLIENT_ID="",
        BOOTSTRAP_ADMIN_EMAIL="",
    )
    assert s.DATABASE_URL == ""
