from app.core.roles import SystemRole
from app.models.user import User
from app.models.organization import Organization
from app.models.org_membership import OrgMembership


def test_user_table_name():
    assert User.__tablename__ == "users"


def test_organization_table_name():
    assert Organization.__tablename__ == "organizations"


def test_org_membership_table_name():
    assert OrgMembership.__tablename__ == "org_memberships"


def test_user_default_role():
    assert User.system_role.default.arg == SystemRole.USER


def test_user_cognito_sub_is_unique():
    col = User.__table__.columns["cognito_sub"]
    assert col.unique is True


def test_org_membership_has_foreign_keys():
    cols = OrgMembership.__table__.columns
    assert cols["org_id"].foreign_keys
    assert cols["user_id"].foreign_keys
