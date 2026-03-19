from functools import lru_cache
from typing import Any

import boto3
from botocore.exceptions import ClientError

from app.core.config import settings

# ── Cognito admin operations (COLD PATH) ──
# These functions run rarely (invites, deletions).
# They make network calls and write to Cognito.


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
