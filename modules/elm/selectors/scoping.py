"""What the caller may see, and which authority they are.

ELM's authorisation is role-based (BR-EL-036). The two
gates -- module grant and permission code -- are checked
by the API; this module decides *scope*: which rows a
permitted caller may actually read or act on.
"""
from __future__ import annotations

from django.db.models import Q, QuerySet

from modules.elm.models import (
    EmployeeProfile,
    LeaveApplication,
    LeaveBalance,
    OrgUnit,
)

# Permission codes are declared in registry.py and enforced
# by the API layer. They are repeated here only as the
# names of the capabilities a scope depends on.
_VIEW_ALL = "elm.application.view"
_VIEW_UNIT = "elm.application.view_unit"
_VIEW_SELF = "elm.application.view_self"
_REVIEW_UNIT_HEAD = "elm.review.unit_head"

#: Permissions whose holder must see every request, because they
#: are asked to decide on requests the system routes to them.
MODULE_WIDE = frozenset({
    "elm.application.view",
    "elm.review.establishment",
    "elm.review.sanction",
    "elm.record.manage",
    "elm.offline.record",
})


def employee_profile(user_id: int) -> EmployeeProfile | None:
    """The employee's ELM profile, if they have one."""
    return EmployeeProfile.objects.filter(
        user_id=user_id).first()


def unit_of(user_id: int) -> OrgUnit | None:
    profile = employee_profile(user_id)
    return profile.unit if profile else None


def is_unit_head_of(user_id: int,
                     applicant_user_id: int) -> bool:
    """Whether ``user_id`` heads the unit ``applicant``
    belongs to."""
    applicant_unit = unit_of(applicant_user_id)
    if applicant_unit is None:
        return False
    return applicant_unit.unit_head_user_id == user_id


def unit_head_for(applicant_user_id: int) -> int | None:
    """The Unit Head of the applicant's unit, if any."""
    applicant_unit = unit_of(applicant_user_id)
    if applicant_unit is None:
        return None
    return applicant_unit.unit_head_user_id


def applications_for(principal) -> QuerySet[LeaveApplication]:
    """The applications the caller may see.

    An employee sees their own. A Unit Head
    additionally sees their unit's -- they
    cannot review what they cannot see. A
    role that decides on requests across the
    module sees every application.
    """
    qs = LeaveApplication.objects.select_related(
        "applicant_unit")
    if principal.has_any_permission(*MODULE_WIDE):
        return qs
    own = Q(user_id=principal.user_id)
    if (principal.has_permission(_VIEW_UNIT)
            or principal.has_permission(_REVIEW_UNIT_HEAD)):
        profile = employee_profile(principal.user_id)
        if profile is not None and profile.unit is not None:
            own |= Q(applicant_unit=profile.unit)
    return qs.filter(own)


def application_for(principal, application_id: int,
                     ) -> LeaveApplication | None:
    """One application, or ``None`` if out of scope."""
    return applications_for(principal).filter(
        pk=application_id).first()


def balances_for(principal) -> QuerySet[LeaveBalance]:
    """Balances the caller may see: their own, or --
    for an administrative role -- everyone's."""
    qs = LeaveBalance.objects.all()
    if principal.has_permission("elm.balance.view"):
        return qs
    return qs.filter(user_id=principal.user_id)


def balance_for(principal, user_id: int, category: str,
                 leave_year: str) -> LeaveBalance | None:
    """One balance, scoped so a foreign employee is a
    404 for anyone but an administrator."""
    qs = balances_for(principal)
    if not principal.has_permission("elm.balance.view"):
        qs = qs.filter(user_id=principal.user_id)
    return qs.filter(user_id=user_id, category=category,
                      leave_year=leave_year).first()


def unit_members(user_id: int) -> QuerySet[EmployeeProfile]:
    """The members of the caller's unit, for a Unit
    Head's work queue."""
    profile = employee_profile(user_id)
    if profile is None or profile.unit is None:
        return EmployeeProfile.objects.none()
    return EmployeeProfile.objects.filter(
        unit=profile.unit)
