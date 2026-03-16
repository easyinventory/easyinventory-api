from unittest.mock import patch, MagicMock
from botocore.exceptions import ClientError

from app.core.cognito import invite_cognito_user


@patch("app.core.cognito.boto3")
@patch("app.core.cognito.settings")
def test_creates_cognito_user(mock_settings, mock_boto3):
    """Should call admin_create_user with correct params."""
    mock_settings.COGNITO_REGION = "us-east-2"
    mock_settings.COGNITO_USER_POOL_ID = "us-east-2_TestPool"
    mock_settings.AWS_ACCESS_KEY_ID = ""
    mock_settings.AWS_SECRET_ACCESS_KEY = ""

    mock_client = MagicMock()
    mock_boto3.client.return_value = mock_client

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


@patch("app.core.cognito.boto3")
@patch("app.core.cognito.settings")
def test_returns_false_if_user_exists(mock_settings, mock_boto3):
    """Should silently return False if Cognito user already exists."""
    mock_settings.COGNITO_REGION = "us-east-2"
    mock_settings.COGNITO_USER_POOL_ID = "us-east-2_TestPool"
    mock_settings.AWS_ACCESS_KEY_ID = ""
    mock_settings.AWS_SECRET_ACCESS_KEY = ""

    mock_client = MagicMock()
    mock_boto3.client.return_value = mock_client

    mock_client.admin_create_user.side_effect = ClientError(
        {"Error": {"Code": "UsernameExistsException", "Message": "User exists"}},
        "AdminCreateUser",
    )

    result = invite_cognito_user("existing@test.com")

    assert result is False


@patch("app.core.cognito.boto3")
@patch("app.core.cognito.settings")
def test_raises_on_other_errors(mock_settings, mock_boto3):
    """Should re-raise non-UsernameExistsException errors."""
    mock_settings.COGNITO_REGION = "us-east-2"
    mock_settings.COGNITO_USER_POOL_ID = "us-east-2_TestPool"
    mock_settings.AWS_ACCESS_KEY_ID = ""
    mock_settings.AWS_SECRET_ACCESS_KEY = ""

    mock_client = MagicMock()
    mock_boto3.client.return_value = mock_client

    mock_client.admin_create_user.side_effect = ClientError(
        {"Error": {"Code": "InternalErrorException", "Message": "Something broke"}},
        "AdminCreateUser",
    )

    try:
        invite_cognito_user("new@test.com")
        assert False, "Should have raised"
    except ClientError as e:
        assert e.response["Error"]["Code"] == "InternalErrorException"


@patch("app.core.cognito.boto3")
@patch("app.core.cognito.settings")
def test_uses_correct_region(mock_settings, mock_boto3):
    """Should create boto3 client with the configured region."""
    mock_settings.COGNITO_REGION = "eu-west-1"
    mock_settings.COGNITO_USER_POOL_ID = "eu-west-1_SomePool"
    mock_settings.AWS_ACCESS_KEY_ID = ""
    mock_settings.AWS_SECRET_ACCESS_KEY = ""

    mock_client = MagicMock()
    mock_boto3.client.return_value = mock_client

    invite_cognito_user("user@test.com")

    mock_boto3.client.assert_called_once_with(
        "cognito-idp",
        region_name="eu-west-1",
        aws_access_key_id=None,
        aws_secret_access_key=None,
    )


@patch("app.core.cognito.boto3")
@patch("app.core.cognito.settings")
def test_uses_configured_aws_credentials(mock_settings, mock_boto3):
    """Should pass AWS credentials to boto3 when configured in settings."""
    mock_settings.COGNITO_REGION = "us-east-2"
    mock_settings.COGNITO_USER_POOL_ID = "us-east-2_TestPool"
    mock_settings.AWS_ACCESS_KEY_ID = "AKIA_TEST_KEY"
    mock_settings.AWS_SECRET_ACCESS_KEY = "TEST_SECRET"

    mock_client = MagicMock()
    mock_boto3.client.return_value = mock_client

    invite_cognito_user("creds@test.com")

    mock_boto3.client.assert_called_once_with(
        "cognito-idp",
        region_name="us-east-2",
        aws_access_key_id="AKIA_TEST_KEY",
        aws_secret_access_key="TEST_SECRET",
    )
