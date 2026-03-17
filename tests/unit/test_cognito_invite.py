from unittest.mock import patch, MagicMock
from botocore.exceptions import ClientError

from app.core.cognito import invite_cognito_user


@patch("app.core.cognito.settings")
@patch("app.core.cognito._get_cognito_client")
def test_creates_cognito_user(mock_get_client, mock_settings):
    """Should call admin_create_user with correct params."""
    mock_settings.COGNITO_REGION = "us-east-2"
    mock_settings.COGNITO_USER_POOL_ID = "us-east-2_TestPool"

    mock_client = MagicMock()
    mock_get_client.return_value = mock_client

    result = invite_cognito_user("new@test.com")

    assert result is True
    mock_client.admin_create_user.assert_called_once()
    call_kwargs = mock_client.admin_create_user.call_args[1]
    assert call_kwargs["Username"] == "new@test.com"
    assert call_kwargs["UserPoolId"] == "us-east-2_TestPool"
    assert call_kwargs["DesiredDeliveryMediums"] == ["EMAIL"]

    # Verify email_verified is set to true
    attrs = call_kwargs["UserAttributes"]
    email_attr = next(a for a in attrs if a["Name"] == "email")
    assert email_attr["Value"] == "new@test.com"
    verified_attr = next(a for a in attrs if a["Name"] == "email_verified")
    assert verified_attr["Value"] == "true"


@patch("app.core.cognito.settings")
@patch("app.core.cognito._get_cognito_client")
def test_returns_false_if_user_exists(mock_get_client, mock_settings):
    """Should resend invite email and return False if Cognito user already exists."""
    mock_settings.COGNITO_REGION = "us-east-2"
    mock_settings.COGNITO_USER_POOL_ID = "us-east-2_TestPool"

    mock_client = MagicMock()
    mock_get_client.return_value = mock_client

    mock_client.admin_create_user.side_effect = [
        ClientError(
            {"Error": {"Code": "UsernameExistsException", "Message": "User exists"}},
            "AdminCreateUser",
        ),
        None,  # RESEND call succeeds
    ]

    result = invite_cognito_user("existing@test.com")

    assert result is False
    assert mock_client.admin_create_user.call_count == 2
    resend_kwargs = mock_client.admin_create_user.call_args_list[1][1]
    assert resend_kwargs["MessageAction"] == "RESEND"
    assert resend_kwargs["Username"] == "existing@test.com"


@patch("app.core.cognito.settings")
@patch("app.core.cognito._get_cognito_client")
def test_raises_on_other_errors(mock_get_client, mock_settings):
    """Should re-raise non-UsernameExistsException errors."""
    mock_settings.COGNITO_REGION = "us-east-2"
    mock_settings.COGNITO_USER_POOL_ID = "us-east-2_TestPool"

    mock_client = MagicMock()
    mock_get_client.return_value = mock_client

    mock_client.admin_create_user.side_effect = ClientError(
        {"Error": {"Code": "InternalErrorException", "Message": "Something broke"}},
        "AdminCreateUser",
    )

    try:
        invite_cognito_user("new@test.com")
        assert False, "Should have raised"
    except ClientError as e:
        assert e.response["Error"]["Code"] == "InternalErrorException"
