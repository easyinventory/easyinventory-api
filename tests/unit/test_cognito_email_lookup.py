"""Tests for cognito email lookup from access token."""

from unittest.mock import patch, MagicMock
from app.core.cognito import get_email_from_access_token


@patch("app.core.cognito._get_cognito_client")
def test_returns_email_from_user_attributes(mock_get_client):
    """Should extract email from Cognito GetUser response."""
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client

    mock_client.get_user.return_value = {
        "UserAttributes": [
            {"Name": "sub", "Value": "abc-123"},
            {"Name": "email", "Value": "user@test.com"},
            {"Name": "email_verified", "Value": "true"},
        ]
    }

    result = get_email_from_access_token("fake-access-token")

    assert result == "user@test.com"
    mock_client.get_user.assert_called_once_with(AccessToken="fake-access-token")


@patch("app.core.cognito._get_cognito_client")
def test_returns_empty_string_on_exception(mock_get_client):
    """Should return '' if the API call fails (don't crash the request)."""
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    mock_client.get_user.side_effect = Exception("Token expired")

    result = get_email_from_access_token("expired-token")

    assert result == ""


@patch("app.core.cognito._get_cognito_client")
def test_returns_empty_string_if_no_email_attribute(mock_get_client):
    """Should return '' if email attribute is missing from response."""
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client

    mock_client.get_user.return_value = {
        "UserAttributes": [
            {"Name": "sub", "Value": "abc-123"},
        ]
    }

    result = get_email_from_access_token("token-no-email")

    assert result == ""
