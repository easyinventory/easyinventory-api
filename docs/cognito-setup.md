# AWS Cognito Setup Guide

## Creating the User Pool

1. Go to AWS Console → Cognito → Create user pool
2. Sign-in: Email only
3. MFA: No MFA
4. Password: Cognito defaults
5. Self-registration: Enabled
6. Verification: Email
7. Email delivery: Send with Cognito (free tier)
8. User pool name: easyinventory-users
9. App client name: easyinventory-web
10. Client type: Public client (no secret)
11. Auth flows: ALLOW_USER_SRP_AUTH, ALLOW_REFRESH_TOKEN_AUTH

## After Creation

Note these three values and add them to your `.env`:

    COGNITO_REGION=us-east-1
    COGNITO_USER_POOL_ID=<your pool id>
    COGNITO_APP_CLIENT_ID=<your client id>

## Creating Test Users

You can create users via the AWS Console:

1. Go to your User Pool → Users → Create user
2. Enter an email address
3. Set a temporary password
4. The user will be prompted to change it on first login

Or via the AWS CLI:

    aws cognito-idp admin-create-user \
      --user-pool-id us-east-1_aBcDeFgHi \
      --username testuser@example.com \
      --user-attributes Name=email,Value=testuser@example.com \
      --temporary-password TempPass123!

## Useful Links

- JWKS endpoint:
  https://cognito-idp.{region}.amazonaws.com/{pool_id}/.well-known/jwks.json
- Issuer URL:
  https://cognito-idp.{region}.amazonaws.com/{pool_id}
- Token endpoint (if needed):
  https://{domain}.auth.{region}.amazoncognito.com/oauth2/token