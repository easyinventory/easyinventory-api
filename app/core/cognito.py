"""
Backward-compatibility shim — re-exports from the new auth module.

All functionality has moved to:
  - app.auth.cognito_token  (hot-path: JWKS, verify, signing key)
  - app.auth.cognito_admin  (cold-path: invite, delete, client)

This file will be removed once all imports are updated.
"""

from app.auth.cognito_admin import (  # noqa: F401
    _get_cognito_client,
    delete_cognito_user,
    invite_cognito_user,
)
from app.auth.cognito_token import (  # noqa: F401
    get_email_from_access_token,
    get_jwks,
    get_signing_key,
    verify_token,
)
