from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "EasyInventory API"
    DEBUG: bool = False
    API_PREFIX: str = "/api"

    # Database (PR-02)
    DATABASE_URL: str = ""

    # Cognito (PR-03)
    COGNITO_REGION: str = ""
    COGNITO_USER_POOL_ID: str = ""
    COGNITO_APP_CLIENT_ID: str = ""

    # AWS credentials (for boto3 — Cognito admin operations)
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""

    # Bootstrap (PR-06)
    BOOTSTRAP_ADMIN_EMAIL: str = ""

    class Config:
        env_file = ".env"


settings = Settings()
