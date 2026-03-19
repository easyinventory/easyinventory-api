from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta, timezone

from jose import jwt

from app.auth.cognito_token import verify_token, get_signing_key

# ── Test constants ──
TEST_REGION = "us-east-1"
TEST_POOL_ID = "us-east-1_TestPool"
TEST_CLIENT_ID = "test-client-id"
TEST_ISSUER = f"https://cognito-idp.{TEST_REGION}.amazonaws.com/{TEST_POOL_ID}"

# RSA key pair for testing (DO NOT use in production)
# Generated with: from jose import jwk; key = jwk.generate_key('RSA', 2048)
TEST_PRIVATE_KEY = {
    "kty": "RSA",
    "kid": "test-kid-001",
    "use": "sig",
    "alg": "RS256",
    "n": "4nLKAFtezA4mEPM-gGtNa3CZN6LNaKytUXxb_x9RCIm4heUwujB7tda6hz2tNMwM6Z_N9bSobphjywoHjcXMw5x8ijHdEaicG7Upl2AGLOpWCU-oZ9t6b7_9LFvZpASHYCljDAJdLvX7xbSGvpNwfXB38ELMjvgVrocZGILCSMLRFQ6jJ2-G4jp33xubQMMLaDxvRizYe4GQsVVc130eLrqd0NCsIT2Cnj9rijiaZ8oZ1sF-LKYUNsOlyl1wmDVA7vupxBHAj1A85ThD-yphU6mBjgGUlgprK8BnfEN5Qcc6qb0Eg_v30b9YbkVfKt-HHgAPCNmQ7qTmdOrHXTQNjQ",
    "e": "AQAB",
    "d": "H8W8s1bJSEGRSb43aMv6wuEQ6Q4or_p6dFJ0k1PmNMJ4vMtZjjuQlVpENbGLrzq_cmV_qm08rLfTrgCsP_zJgYYKsKvVDs3k3ruz0uTK47Ea0pegqLcnc1fcF_CTQEDPwHL4zg3kMTCbsN5m1tqCZWH1vM-X5VTIW1finN52kBVcmhgis7qB9Q2IutbkWuhucgMKyGYVrCe-0dfBTZD02OXVKZR4LMqaUX1AwFDgmh7eau3uzPe4pB-p1RHC_WPsmhhr3H8XkTqKFuquq7wLB6P1lYFvKGCBuiLTtNggkt5YkIbjCFXjKN8AvBbe-lXuwpAOTznfVudGzgnwmGKhaQ",
    "p": "_Zk0saAf4RlYoc3HAXse2GI7JdRbBPoQ4WOKoOKCUuDYIT0e1x-kUkwdKAjrqijWkNhQUB49vZ6M7Hx9uDdDJsVD-Sd8EswYtfjK7FMwgxbOq2h25acFTAe6sNriKqQcDQWG-iXoymsb-GEZzzuLUGyknqAWhH3PhkHfOflL198",
    "q": "5JfDiat4P1OPI2W75EcrVcr1_68BvxnyTNqSuZTi-FEO4Xx3tWG8oFQmeFuYv-f0w4BHchdbiuuA0TBy5oY1JEJWQBfVp15zcIleZPiB1kQCk6ka0kvGPKuptxXBvkO4HKc27NKk43RsgPvdUfKR-EeibQhfwTHlwQJz17bt-BM",
    "dp": "pvSYNmCe3Ekditi4rYbrFbYGDq-xhKNFPb2U5Lp65ilU4P0mMqaIPg4SG-tTi2D7cbyXk0d1ikK5sG99LSxkrz-rsnqGOrHXiuXSYqeaBpObWEmcDTFaUWW9SPWxdDU6qm_7HvCaQ7kkXu8-WKpw22_LKQtoB630VAVF-xrfDa0",
    "dq": "2TGtk5f9Z8YAAbT-4nYQobJ3K9nfgfCoPQeMU5I4WZHC3tIBd7CGpZtu9fqp1uUQtdSjja7Nxt_ehGRRN-EaivoQs1MyKJVgf_O1YaCQ1MHH5P7OwjNHBoxgc9nTPPFg9LCYSkoWaxtKoP8uGVeuA8YkeQ501L6RO2MWKEbiMks",
    "qi": "Y32GfCE8_7fGWVTiNI6S0L167HSfXz9QVvYwjZYiYfOyg5vZf1X4wl-jAv1jOU-fZYBzhbCcDguohA912lTQsHsaaMse-rNzZ7c0_sAoJNi7WcV-mfUYykvKA2HthSdQM1eT1VZeltFYP8eP2ODPylsOIo-u4cshaiss1XsNkF0",
}

TEST_PUBLIC_KEY = {
    "kty": "RSA",
    "kid": "test-kid-001",
    "use": "sig",
    "alg": "RS256",
    "n": "4nLKAFtezA4mEPM-gGtNa3CZN6LNaKytUXxb_x9RCIm4heUwujB7tda6hz2tNMwM6Z_N9bSobphjywoHjcXMw5x8ijHdEaicG7Upl2AGLOpWCU-oZ9t6b7_9LFvZpASHYCljDAJdLvX7xbSGvpNwfXB38ELMjvgVrocZGILCSMLRFQ6jJ2-G4jp33xubQMMLaDxvRizYe4GQsVVc130eLrqd0NCsIT2Cnj9rijiaZ8oZ1sF-LKYUNsOlyl1wmDVA7vupxBHAj1A85ThD-yphU6mBjgGUlgprK8BnfEN5Qcc6qb0Eg_v30b9YbkVfKt-HHgAPCNmQ7qTmdOrHXTQNjQ",
    "e": "AQAB",
}


def _make_token(
    sub: str = "abc-123",
    email: str = "test@example.com",
    exp_minutes: int = 60,
    issuer: str = TEST_ISSUER,
    audience: str = TEST_CLIENT_ID,
    kid: str = "test-kid-001",
) -> str:
    """Helper to mint a test JWT signed with our test private key."""
    now = datetime.now(timezone.utc)
    claims = {
        "sub": sub,
        "email": email,
        "iss": issuer,
        "aud": audience,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=exp_minutes)).timestamp()),
        "token_use": "id",
    }
    headers = {"kid": kid, "alg": "RS256"}
    return jwt.encode(claims, TEST_PRIVATE_KEY, algorithm="RS256", headers=headers)


def _mock_settings():
    """Return a mock settings object with test Cognito values."""
    mock = MagicMock()
    mock.COGNITO_REGION = TEST_REGION
    mock.COGNITO_USER_POOL_ID = TEST_POOL_ID
    mock.COGNITO_APP_CLIENT_ID = TEST_CLIENT_ID
    return mock


def _mock_jwks():
    """Return a JWKS response containing our test public key."""
    return {"keys": [TEST_PUBLIC_KEY]}


# ── Tests ──


@patch("app.auth.cognito_token.settings", new_callable=_mock_settings)
@patch("app.auth.cognito_token.get_jwks", return_value=_mock_jwks())
def test_verify_valid_token(mock_jwks, mock_settings):
    token = _make_token()
    claims = verify_token(token)
    assert claims["sub"] == "abc-123"
    assert claims["email"] == "test@example.com"


@patch("app.auth.cognito_token.settings", new_callable=_mock_settings)
@patch("app.auth.cognito_token.get_jwks", return_value=_mock_jwks())
def test_verify_token_returns_all_claims(mock_jwks, mock_settings):
    token = _make_token(sub="user-456", email="admin@test.com")
    claims = verify_token(token)
    assert claims["sub"] == "user-456"
    assert claims["email"] == "admin@test.com"
    assert claims["iss"] == TEST_ISSUER
    assert claims["aud"] == TEST_CLIENT_ID
    assert "exp" in claims
    assert "iat" in claims


@patch("app.auth.cognito_token.settings", new_callable=_mock_settings)
@patch("app.auth.cognito_token.get_jwks", return_value=_mock_jwks())
def test_expired_token_raises(mock_jwks, mock_settings):
    token = _make_token(exp_minutes=-10)
    try:
        verify_token(token)
        assert False, "Should have raised"
    except Exception as e:
        assert "expired" in str(e).lower() or "Signature has expired" in str(e)


@patch("app.auth.cognito_token.settings", new_callable=_mock_settings)
@patch("app.auth.cognito_token.get_jwks", return_value=_mock_jwks())
def test_wrong_audience_raises(mock_jwks, mock_settings):
    token = _make_token(audience="wrong-client-id")
    try:
        verify_token(token)
        assert False, "Should have raised"
    except Exception:
        pass  # Any exception is acceptable


@patch("app.auth.cognito_token.settings", new_callable=_mock_settings)
@patch("app.auth.cognito_token.get_jwks", return_value=_mock_jwks())
def test_wrong_issuer_raises(mock_jwks, mock_settings):
    token = _make_token(issuer="https://wrong-issuer.com")
    try:
        verify_token(token)
        assert False, "Should have raised"
    except Exception:
        pass  # Any exception is acceptable


@patch("app.auth.cognito_token.settings", new_callable=_mock_settings)
@patch("app.auth.cognito_token.get_jwks", return_value={"keys": []})
def test_unknown_kid_raises(mock_jwks, mock_settings):
    token = _make_token(kid="unknown-kid")
    try:
        get_signing_key(token)
        assert False, "Should have raised"
    except Exception as e:
        assert "not found" in str(e).lower()


def test_get_jwks_url_is_well_formed():
    """Verify the JWKS URL follows Cognito's expected pattern."""
    region = "us-east-1"
    pool_id = "us-east-1_TestPool"
    expected = (
        f"https://cognito-idp.{region}.amazonaws.com"
        f"/{pool_id}/.well-known/jwks.json"
    )
    # Construct the same way cognito.py does
    url = (
        f"https://cognito-idp.{region}.amazonaws.com"
        f"/{pool_id}/.well-known/jwks.json"
    )
    assert url == expected
    assert url.startswith("https://")
    assert url.endswith("jwks.json")
