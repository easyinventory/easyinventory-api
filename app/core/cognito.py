from functools import lru_cache

import requests
from jose import jwt, JWTError
from typing import Any
from app.core.config import settings


@lru_cache(maxsize=1)
def get_jwks() -> dict[str, Any]:
    """
    Fetch Cognito's public keys (JWKS).

    Cached so we only hit the network once per process lifetime.
    The keys rotate infrequently — restarting the app refreshes them.
    """
    url = (
        f"https://cognito-idp.{settings.COGNITO_REGION}.amazonaws.com"
        f"/{settings.COGNITO_USER_POOL_ID}/.well-known/jwks.json"
    )
    response = requests.get(url, timeout=5)
    response.raise_for_status()
    result: dict[str, Any] = response.json()
    return result


def get_signing_key(token: str) -> dict[str, Any]:
    """
    Find the correct public key for this token's key ID (kid).
    """
    jwks = get_jwks()
    headers = jwt.get_unverified_headers(token)
    kid = headers.get("kid")

    for key in jwks.get("keys", []):
        if key["kid"] == kid:
            result: dict[str, Any] = key
            return result

    raise JWTError(f"Public key not found for kid: {kid}")


def verify_token(token: str) -> dict[str, Any]:
    """
    Decode and verify a Cognito JWT.

    Validates:
    - Signature (using Cognito's public key)
    - Expiration (exp claim)
    - Issuer (iss must match our User Pool)
    - Audience (client_id must match our App Client)

    Returns the decoded claims dict on success.
    Raises JWTError on any failure.
    """
    signing_key = get_signing_key(token)

    issuer = (
        f"https://cognito-idp.{settings.COGNITO_REGION}.amazonaws.com"
        f"/{settings.COGNITO_USER_POOL_ID}"
    )

    claims: dict[str, Any] = jwt.decode(
        token,
        signing_key,
        algorithms=["RS256"],
        audience=settings.COGNITO_APP_CLIENT_ID,
        issuer=issuer,
    )
    return claims
