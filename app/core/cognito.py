from functools import lru_cache
from typing import Any

import boto3
import requests
from botocore.exceptions import ClientError
from jose import jwt, JWTError

from app.core.config import settings

# ── Cached Cognito client ──


@lru_cache(maxsize=1)
def _get_cognito_client() -> Any:
    """
    Return a cached boto3 cognito-idp client.

    Cached so we don't spin up a new client on every request.
    """
    return boto3.client(
        "cognito-idp",
        region_name=settings.COGNITO_REGION,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID or None,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY or None,
    )


# ── JWKS / Token verification ──


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


# ── Email lookup from access token ──


def get_email_from_access_token(access_token: str) -> str:
    """
    Retrieve the user's email from Cognito using an access token.

    Cognito access tokens don't include the email claim (only ID tokens
    do). This function calls Cognito's GetUser API to look it up.

    Returns the email string, or "" if the lookup fails.
    """
    try:
        client = _get_cognito_client()
        resp = client.get_user(AccessToken=access_token)
        return next(
            (
                attr["Value"]
                for attr in resp["UserAttributes"]
                if attr["Name"] == "email"
            ),
            "",
        )
    except Exception:
        return ""


# ── User invite ──


def invite_cognito_user(email: str) -> bool:
    """
    Create a Cognito user account and send an invite email
    with a temporary password.

    Cognito sends an email like:
      "Your administrator has invited you to join EasyInventory.
       Your username is: <email>
       Your temporary password is: <temp_password>
       Sign in at: <login_url>"

    Returns True if the user was created, False if they already exist.
    """
    client = _get_cognito_client()

    try:
        client.admin_create_user(
            UserPoolId=settings.COGNITO_USER_POOL_ID,
            Username=email,
            UserAttributes=[
                {"Name": "email", "Value": email},
                {"Name": "email_verified", "Value": "true"},
            ],
            DesiredDeliveryMediums=["EMAIL"],
        )
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] == "UsernameExistsException":
            # User already has a Cognito account — resend the invite email
            client.admin_create_user(
                UserPoolId=settings.COGNITO_USER_POOL_ID,
                Username=email,
                MessageAction="RESEND",
                DesiredDeliveryMediums=["EMAIL"],
            )
            return False
        raise


# ── User deletion ──


def delete_cognito_user(email: str, cognito_sub: str) -> None:
    """
    Delete a Cognito user account.

    We first try email (most pools use email as username), then fall back
    to cognito_sub for environments configured differently.
    """
    client = _get_cognito_client()

    candidate_usernames = [email]
    if cognito_sub and not cognito_sub.startswith("pending:"):
        candidate_usernames.append(cognito_sub)

    for username in candidate_usernames:
        try:
            client.admin_delete_user(
                UserPoolId=settings.COGNITO_USER_POOL_ID,
                Username=username,
            )
            return
        except ClientError as e:
            if e.response["Error"]["Code"] == "UserNotFoundException":
                continue
            raise
