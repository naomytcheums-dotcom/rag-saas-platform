"""Reject unsafe pre-existing roles before staging RLS grants are applied."""

import pytest

from scripts.staging_target import StagingTargetError
from scripts.staging_validate import validate_tenant_role

FLAGS = ("rolcanlogin", "rolsuper", "rolbypassrls", "rolcreatedb", "rolcreaterole")


def test_restricted_staging_role_is_accepted():
    validate_tenant_role(dict.fromkeys(FLAGS, False), False, False)


@pytest.mark.parametrize("flag", FLAGS)
def test_privileged_or_login_role_is_rejected(flag):
    flags = dict.fromkeys(FLAGS, False)
    flags[flag] = True
    with pytest.raises(StagingTargetError, match="refused"):
        validate_tenant_role(flags, False, False)


@pytest.mark.parametrize("memberships,owns_tables", [(True, False), (False, True)])
def test_assumable_or_table_owner_role_is_rejected(memberships, owns_tables):
    with pytest.raises(StagingTargetError, match="refused"):
        validate_tenant_role(dict.fromkeys(FLAGS, False), memberships, owns_tables)
