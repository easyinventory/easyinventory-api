from app.core.config import Settings


def test_default_app_name():
    s = Settings(
        DATABASE_URL="",
        COGNITO_REGION="",
        COGNITO_USER_POOL_ID="",
        COGNITO_APP_CLIENT_ID="",
        BOOTSTRAP_ADMIN_EMAIL="",
    )
    assert s.APP_NAME == "EasyInventory API"


def test_default_debug_is_false():
    s = Settings(
        DATABASE_URL="",
        COGNITO_REGION="",
        COGNITO_USER_POOL_ID="",
        COGNITO_APP_CLIENT_ID="",
        BOOTSTRAP_ADMIN_EMAIL="",
    )
    assert s.DEBUG is False


def test_default_api_prefix():
    s = Settings(
        DATABASE_URL="",
        COGNITO_REGION="",
        COGNITO_USER_POOL_ID="",
        COGNITO_APP_CLIENT_ID="",
        BOOTSTRAP_ADMIN_EMAIL="",
    )
    assert s.API_PREFIX == "/api"


def test_debug_can_be_overridden():
    s = Settings(
        DEBUG=True,
        DATABASE_URL="",
        COGNITO_REGION="",
        COGNITO_USER_POOL_ID="",
        COGNITO_APP_CLIENT_ID="",
        BOOTSTRAP_ADMIN_EMAIL="",
    )
    assert s.DEBUG is True
