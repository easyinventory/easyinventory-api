"""
Invite orchestration service.

Consolidates the "find or create user → Cognito invite → create
membership" flow that was duplicated in admin.py and orgs.py into
a single, testable service function.
"""

from __future__ import annotations

import asyncio
import uuid
from functools import partial

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cognito import invite_cognito_user
from app.core.exceptions import AlreadyExists
from app.models.org_membership import OrgMembership
from app.services import org_service


async def invite_user_to_org(
    db: AsyncSession,
    org_id: uuid.UUID,
    email: str,
    org_role: str,
    *,
    is_new_org: bool = False,
) -> OrgMembership:
    """
    Invite a user to an org by email.

    Handles three cases:
      1. User exists and is NOT a member → active membership
      2. User exists and IS a member → raise AlreadyExists
      3. User doesn't exist → Cognito invite + placeholder + inactive membership

    Args:
        db: Active database session
        org_id: The organization to add them to
        email: The invitee's email address
        org_role: Role to assign (e.g. OrgRole.OWNER, OrgRole.EMPLOYEE)
        is_new_org: If True, skip the duplicate-membership check
                    (org was just created so no members can exist)

    Returns:
        The created OrgMembership

    Raises:
        AlreadyExists: If the user is already a member (active or pending)
    """
    existing_user = await org_service.find_user_by_email(db, email)

    if existing_user:
        if not is_new_org:
            existing_membership = await org_service.find_existing_membership(
                db, org_id, existing_user.id
            )
            if existing_membership:
                if existing_membership.is_active:
                    raise AlreadyExists("User is already a member of this organization")
                else:
                    raise AlreadyExists(
                        "This user has already been invited. "
                        "They will gain access when they sign up."
                    )

        # Known user, not yet a member → active membership
        return await org_service.create_membership(
            db=db,
            org_id=org_id,
            user_id=existing_user.id,
            org_role=org_role,
            is_active=True,
        )

    # Unknown email → Cognito invite + placeholder + inactive membership
    # invite_cognito_user is a blocking boto3 call; run it in a thread-pool
    # executor so it doesn't stall the async event loop.
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, partial(invite_cognito_user, email))
    placeholder = await org_service.create_placeholder_user(db, email)
    return await org_service.create_membership(
        db=db,
        org_id=org_id,
        user_id=placeholder.id,
        org_role=org_role,
        is_active=False,
    )
