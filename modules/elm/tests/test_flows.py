"""The ELM flows, against the database.

Covers the parts where a rule meets a row: submission and its
gates, the substitute consent gate, the Unit Head / final
decision paths, balance movement, cancellation, extension and
resumption.
"""
from datetime import date, timedelta

import pytest

from conftest import make_principal
from core.api.exceptions import (
    ConflictError,
    PermissionDeniedError,
)
from modules.elm.domain import state_machine as sm
from modules.elm.models import (
    EmployeeProfile,
    LeaveApplication,
    LeaveBalance,
    OrgUnit,
)
from modules.elm.services import applications as app_service
from modules.elm.services import cancellations as cancel_service
from modules.elm.services import decisions as decision_service
from modules.elm.services import extensions as extension_service
from modules.elm.services import offline as offline_service
from modules.elm.services import resumptions as resumption_service
from modules.elm.services import year_end as year_end_service

pytestmark = pytest.mark.django_db

APPLICANT = 2001
UNIT_HEAD = 2002
DIRECTOR = 2003
SUBSTITUTE = 2004
FACULTY = 2005

# A Monday well in the future, so nothing is "ongoing" by accident.
START = date.today() + timedelta(days=30)
END = START + timedelta(days=1)


def unit(code="CSE", head=UNIT_HEAD):
    return OrgUnit.objects.create(
        code=code, name=f"{code} Department",
        unit_head_user_id=head)


def employee(user_id, designation="Lecturer",
             category="staff", org=None):
    return EmployeeProfile.objects.create(
        user_id=user_id, designation=designation,
        category=category, unit=org)


def principal(user_id, permissions=(), roles=("employee",)):
    return make_principal(
        user_id=user_id, kind="staff",
        permissions=frozenset(permissions), roles=tuple(roles),
        active_role=roles[0] if roles else None)


APPLY = ["elm.application.create"]
VIEW_SELF = ["elm.application.view_self"]
VIEW_UNIT = ["elm.application.view_unit"]
VIEW_ALL = ["elm.application.view"]
UNIT_HEAD_PERMS = ["elm.review.unit_head"]
SANCTION = ["elm.review.sanction"]

#: What a real employee holds: their own leave activity.
EMPLOYEE_PERMS = [
    "elm.application.create",
    "elm.application.view_self",
    "elm.application.withdraw",
    "elm.application.cancel_request",
    "elm.extension.request",
    "elm.resumption.submit",
    "elm.application.export",
]


@pytest.fixture
def org():
    return unit()


@pytest.fixture
def applicant(org):
    employee(APPLICANT, org=org)
    return principal(APPLICANT, EMPLOYEE_PERMS)


@pytest.fixture
def head(org):
    employee(UNIT_HEAD, designation="HOD", org=org)
    return principal(UNIT_HEAD, UNIT_HEAD_PERMS + VIEW_SELF)


@pytest.fixture
def director(org):
    employee(DIRECTOR, designation="director", org=org)
    return principal(DIRECTOR, SANCTION + APPLY + VIEW_SELF,
                     roles=("director",))


class TestSubmission:

    def test_a_plain_cl_request_lands_with_the_unit_head(
            self, applicant, head):
        """BW-EL-01: CL/RH with no substitute gate."""
        leave = app_service.submit(
            principal=applicant, category="CL",
            start_date=START, end_date=END,
            purpose="Family matter")
        assert leave.status == sm.AWAITING_UNIT_HEAD
        assert leave.days_requested == 2.0
        assert leave.purpose == "Family matter"

    def test_an_employee_without_the_grant_cannot_apply(
            self, org):
        """BR-EL-036: the grant is the authority."""
        employee(APPLICANT, org=org)
        with pytest.raises(PermissionDeniedError):
            app_service.submit(
                principal=principal(APPLICANT, VIEW_SELF),
                category="CL",
                start_date=START, end_date=END)

    def test_an_unsupported_category_is_refused(self, applicant):
        with pytest.raises(ConflictError) as exc:
            app_service.submit(
                principal=applicant, category="ML",
                start_date=START, end_date=END)
        assert exc.value.code == "unsupported_category"

    def test_requesting_more_than_the_entitlement_is_refused(
            self, applicant):
        """BR-EL-002: CL is 8 days a year."""
        with pytest.raises(ConflictError) as exc:
            app_service.submit(
                principal=applicant, category="CL",
                start_date=START, end_date=START + timedelta(
                    days=20))
        assert exc.value.code == "insufficient_balance"

    def test_an_overlapping_request_is_refused(self, applicant):
        app_service.submit(
            principal=applicant, category="CL",
            start_date=START, end_date=END)
        with pytest.raises(ConflictError) as exc:
            app_service.submit(
                principal=applicant, category="CL",
                start_date=START + timedelta(days=1),
                end_date=END + timedelta(days=1))
        assert exc.value.code == "leave_overlap"

    def test_a_half_day_consumes_half_a_day(self, applicant):
        leave = app_service.submit(
            principal=applicant, category="CL",
            start_date=START, end_date=START,
            half_day="first")
        assert leave.days_requested == 0.5

    def test_both_halves_of_one_cl_day_may_be_taken(
            self, applicant):
        """BR-EL-012: the halves do not overlap."""
        app_service.submit(
            principal=applicant, category="CL",
            start_date=START, end_date=START,
            half_day="first")
        leave = app_service.submit(
            principal=applicant, category="CL",
            start_date=START, end_date=START,
            half_day="second")
        assert leave.status == sm.AWAITING_UNIT_HEAD

    def test_a_station_leave_is_captured_in_the_same_application(
            self, applicant):
        """BR-EL-013: not a separate request."""
        leave = app_service.submit(
            principal=applicant, category="CL",
            start_date=START, end_date=END,
            station_leave=True,
            station_leave_details="Delhi, 4 days")
        assert leave.station_leave
        assert "Delhi" in leave.station_leave_details


class TestSubstituteGate:

    def test_a_nominated_substitute_holds_the_request(
            self, org, applicant):
        """BW-EL-02: awaiting consent, not the Unit Head."""
        employee(SUBSTITUTE, org=org)
        leave = app_service.submit(
            principal=applicant, category="EL",
            start_date=START, end_date=END,
            substitute_required=True,
            substitute_user_id=SUBSTITUTE)
        assert leave.status == sm.AWAITING_SUBSTITUTE

    def test_acceptance_releases_the_gate(self, org, applicant,
                                          head):
        employee(SUBSTITUTE, org=org)
        leave = app_service.submit(
            principal=applicant, category="EL",
            start_date=START, end_date=END,
            substitute_required=True,
            substitute_user_id=SUBSTITUTE)
        sub = leave.substitute_assignments.first()
        app_service.respond_to_substitute(
            principal=principal(SUBSTITUTE, VIEW_SELF),
            assignment_id=sub.pk, accept=True)
        leave.refresh_from_db()
        assert leave.status == sm.AWAITING_UNIT_HEAD

    def test_a_decline_holds_the_gate_closed_and_asks_for_a_nominee(
            self, org, applicant):
        """BR-EL-015: decline does not release routing."""
        employee(SUBSTITUTE, org=org)
        leave = app_service.submit(
            principal=applicant, category="EL",
            start_date=START, end_date=END,
            substitute_required=True,
            substitute_user_id=SUBSTITUTE)
        sub = leave.substitute_assignments.first()
        app_service.respond_to_substitute(
            principal=principal(SUBSTITUTE, VIEW_SELF),
            assignment_id=sub.pk, accept=False,
            decline_reason="Teaching")
        leave.refresh_from_db()
        assert leave.status == sm.APPLICANT_ACTION

    def test_a_replacement_reopens_the_gate_once(self, org,
                                                 applicant):
        """BW-EL-03 / EL-UC-019."""
        employee(SUBSTITUTE, org=org)
        employee(FACULTY, designation="Reader", org=org)
        leave = app_service.submit(
            principal=applicant, category="EL",
            start_date=START, end_date=END,
            substitute_required=True,
            substitute_user_id=SUBSTITUTE)
        app_service.respond_to_substitute(
            principal=principal(SUBSTITUTE, VIEW_SELF),
            assignment_id=leave.substitute_assignments.first().pk,
            accept=False)
        app_service.nominate_replacement(
            principal=applicant, application_id=leave.pk,
            substitute_user_id=FACULTY)
        leave.refresh_from_db()
        assert leave.status == sm.AWAITING_SUBSTITUTE

    def test_a_stale_substitute_response_is_refused(self, org,
                                                   applicant):
        employee(SUBSTITUTE, org=org)
        leave = app_service.submit(
            principal=applicant, category="EL",
            start_date=START, end_date=END,
            substitute_required=True,
            substitute_user_id=SUBSTITUTE)
        sub = leave.substitute_assignments.first()
        sub_principal = principal(SUBSTITUTE, VIEW_SELF)
        app_service.respond_to_substitute(
            principal=sub_principal,
            assignment_id=sub.pk, accept=True)
        with pytest.raises(ConflictError):
            app_service.respond_to_substitute(
                principal=sub_principal,
                assignment_id=sub.pk, accept=False)


class TestUnitHeadReview:

    def test_cl_is_decided_outright_by_the_unit_head(self,
                                                     applicant, head):
        """BR-EL-016."""
        leave = app_service.submit(
            principal=applicant, category="CL",
            start_date=START, end_date=END)
        decision_service.unit_head_review(
            principal=head, application_id=leave.pk,
            outcome="approve")
        leave.refresh_from_db()
        assert leave.status == sm.APPROVED

    def test_an_approved_cl_deducts_the_balance(self, applicant,
                                                head):
        leave = app_service.submit(
            principal=applicant, category="CL",
            start_date=START, end_date=END)
        decision_service.unit_head_review(
            principal=head, application_id=leave.pk,
            outcome="approve")
        balance = LeaveBalance.objects.get(
            user_id=APPLICANT, category="CL")
        assert balance.used == 2.0
        assert balance.available == 6.0

    def test_a_rejected_cl_leaves_the_balance_untouched(
            self, applicant, head):
        leave = app_service.submit(
            principal=applicant, category="CL",
            start_date=START, end_date=END)
        decision_service.unit_head_review(
            principal=head, application_id=leave.pk,
            outcome="reject")
        balance = LeaveBalance.objects.get(
            user_id=APPLICANT, category="CL")
        assert balance.used == 0.0

    def test_higher_sanction_leave_is_only_recommended(self,
                                                       applicant,
                                                       head):
        """BR-EL-017: EL does not stop at the Unit Head."""
        leave = app_service.submit(
            principal=applicant, category="EL",
            start_date=START, end_date=END)
        decision_service.unit_head_review(
            principal=head, application_id=leave.pk,
            recommendation="recommended")
        leave.refresh_from_db()
        assert leave.status == sm.AWAITING_FINAL
        assert leave.recommendation == "recommended"

    def test_not_recommended_is_not_a_rejection(self, applicant,
                                                head):
        leave = app_service.submit(
            principal=applicant, category="EL",
            start_date=START, end_date=END)
        decision_service.unit_head_review(
            principal=head, application_id=leave.pk,
            recommendation="not_recommended")
        leave.refresh_from_db()
        assert leave.status == sm.AWAITING_FINAL
        assert leave.status != sm.REJECTED

    def test_a_higher_sanction_review_needs_a_recommendation(
            self, applicant, head):
        leave = app_service.submit(
            principal=applicant, category="EL",
            start_date=START, end_date=END)
        with pytest.raises(ConflictError):
            decision_service.unit_head_review(
                principal=head, application_id=leave.pk,
                outcome="approve")

    def test_a_stranger_cannot_review_someone_elses_leave(
            self, applicant, org):
        """BR-EL-036: someone who can see the request is still
        not its Unit Head."""
        other = unit("PHYS", head=9999)
        employee(9999, designation="HOD", org=other)
        leave = app_service.submit(
            principal=applicant, category="CL",
            start_date=START, end_date=END)
        with pytest.raises(PermissionDeniedError):
            decision_service.unit_head_review(
                principal=principal(
                    9999, UNIT_HEAD_PERMS + VIEW_ALL),
                application_id=leave.pk, outcome="approve")


class TestWithdrawal:

    def test_withdrawal_is_immediate_and_terminal(self, applicant):
        """BR-EL-022."""
        leave = app_service.submit(
            principal=applicant, category="CL",
            start_date=START, end_date=END)
        app_service.withdraw(
            principal=applicant, application_id=leave.pk,
            reason="Plans changed")
        leave.refresh_from_db()
        assert leave.status == sm.WITHDRAWN

    def test_an_approved_leave_can_no_longer_be_withdrawn(
            self, applicant, head):
        leave = app_service.submit(
            principal=applicant, category="CL",
            start_date=START, end_date=END)
        decision_service.unit_head_review(
            principal=head, application_id=leave.pk,
            outcome="approve")
        with pytest.raises(ConflictError):
            app_service.withdraw(
                principal=applicant, application_id=leave.pk)

    def test_someone_else_cannot_withdraw_your_leave(
            self, applicant, head):
        """The Unit Head can see their unit's leave (they must,
        to review it) but may not withdraw it."""
        leave = app_service.submit(
            principal=applicant, category="CL",
            start_date=START, end_date=END)
        with pytest.raises(PermissionDeniedError):
            app_service.withdraw(
                principal=head, application_id=leave.pk)


class TestSanction:

    def test_a_final_approval_updates_the_account(self, applicant,
                                                  head, director):
        leave = app_service.submit(
            principal=applicant, category="EL",
            start_date=START, end_date=END)
        decision_service.unit_head_review(
            principal=head, application_id=leave.pk,
            recommendation="recommended")
        decision_service.final_sanction(
            principal=director, application_id=leave.pk,
            outcome="approve")
        leave.refresh_from_db()
        assert leave.status == sm.APPROVED
        assert LeaveBalance.objects.get(
            user_id=APPLICANT, category="EL").used == 2.0

    def test_a_final_rejection_preserves_the_balance(
            self, applicant, head, director):
        leave = app_service.submit(
            principal=applicant, category="EL",
            start_date=START, end_date=END)
        decision_service.unit_head_review(
            principal=head, application_id=leave.pk,
            recommendation="recommended")
        decision_service.final_sanction(
            principal=director, application_id=leave.pk,
            outcome="reject")
        leave.refresh_from_db()
        assert leave.status == sm.REJECTED
        assert LeaveBalance.objects.get(
            user_id=APPLICANT, category="EL").used == 0.0

    def test_a_director_leave_self_sanctions(self, org, director):
        """BR-EL-020."""
        leave = app_service.submit(
            principal=director, category="EL",
            start_date=START, end_date=END)
        assert leave.status == sm.AWAITING_DIRECTOR
        decision_service.final_sanction(
            principal=director, application_id=leave.pk,
            outcome="approve")
        leave.refresh_from_db()
        assert leave.status == sm.APPROVED


class TestCancellation:

    def test_cancelling_an_approved_leave_restores_the_balance(
            self, applicant, head, director):
        leave = app_service.submit(
            principal=applicant, category="EL",
            start_date=START, end_date=END)
        decision_service.unit_head_review(
            principal=head, application_id=leave.pk,
            recommendation="recommended")
        decision_service.final_sanction(
            principal=director, application_id=leave.pk,
            outcome="approve")
        cancellation = cancel_service.request_cancellation(
            principal=applicant, leave_id=leave.pk,
            reason="Trip cancelled")
        cancel_service.final_cancellation(
            principal=director, cancellation_id=cancellation.pk,
            outcome="approve")
        leave.refresh_from_db()
        assert leave.status == sm.CANCELLED
        assert LeaveBalance.objects.get(
            user_id=APPLICANT, category="EL").used == 0.0

    def test_a_rejected_cancellation_leaves_the_leave_alone(
            self, applicant, head, director):
        leave = app_service.submit(
            principal=applicant, category="EL",
            start_date=START, end_date=END)
        decision_service.unit_head_review(
            principal=head, application_id=leave.pk,
            recommendation="recommended")
        decision_service.final_sanction(
            principal=director, application_id=leave.pk,
            outcome="approve")
        cancellation = cancel_service.request_cancellation(
            principal=applicant, leave_id=leave.pk)
        cancel_service.final_cancellation(
            principal=director, cancellation_id=cancellation.pk,
            outcome="reject")
        leave.refresh_from_db()
        assert leave.status == sm.APPROVED
        assert LeaveBalance.objects.get(
            user_id=APPLICANT, category="EL").used == 2.0

    def test_a_pending_leave_cannot_be_cancelled(self, applicant):
        """Cancellation applies to an approved leave, not a
        pending one."""
        leave = app_service.submit(
            principal=applicant, category="EL",
            start_date=START, end_date=END)
        with pytest.raises(ConflictError):
            cancel_service.request_cancellation(
                principal=applicant, leave_id=leave.pk)


class TestExtension:

    def test_an_extension_posts_only_the_incremental_period(
            self, applicant, head, director):
        """BR-EL-025."""
        leave = app_service.submit(
            principal=applicant, category="EL",
            start_date=START, end_date=END)
        decision_service.unit_head_review(
            principal=head, application_id=leave.pk,
            recommendation="recommended")
        decision_service.final_sanction(
            principal=director, application_id=leave.pk,
            outcome="approve")
        leave.status = sm.ONGOING
        leave.save(update_fields=["status"])

        extension = extension_service.request_extension(
            principal=applicant, leave_id=leave.pk,
            additional_start=END + timedelta(days=1),
            additional_end=END + timedelta(days=2))
        assert extension.additional_days == 2.0
        extension_service.unit_head_extension(
            principal=head, extension_id=extension.pk,
            recommendation="recommended")
        extension_service.final_extension(
            principal=director, extension_id=extension.pk,
            outcome="approve")

        leave.refresh_from_db()
        assert leave.end_date == END + timedelta(days=2)
        # 2 days for the base plus 2 more for the extension.
        assert LeaveBalance.objects.get(
            user_id=APPLICANT, category="EL").used == 4.0

    def test_a_rejected_extension_preserves_the_original_leave(
            self, applicant, head, director):
        leave = app_service.submit(
            principal=applicant, category="EL",
            start_date=START, end_date=END)
        decision_service.unit_head_review(
            principal=head, application_id=leave.pk,
            recommendation="recommended")
        decision_service.final_sanction(
            principal=director, application_id=leave.pk,
            outcome="approve")
        leave.status = sm.ONGOING
        leave.save(update_fields=["status"])
        extension = extension_service.request_extension(
            principal=applicant, leave_id=leave.pk,
            additional_start=END + timedelta(days=1),
            additional_end=END + timedelta(days=1))
        extension_service.unit_head_extension(
            principal=head, extension_id=extension.pk,
            recommendation="recommended")
        extension_service.final_extension(
            principal=director, extension_id=extension.pk,
            outcome="reject")
        leave.refresh_from_db()
        assert leave.end_date == END
        assert LeaveBalance.objects.get(
            user_id=APPLICANT, category="EL").used == 2.0

    def test_cl_cannot_be_extended(self, applicant, head):
        """Only EL/COL/VL may be extended."""
        leave = app_service.submit(
            principal=applicant, category="CL",
            start_date=START, end_date=END)
        decision_service.unit_head_review(
            principal=head, application_id=leave.pk,
            outcome="approve")
        leave.status = sm.ONGOING
        leave.save(update_fields=["status"])
        with pytest.raises(ConflictError) as exc:
            extension_service.request_extension(
                principal=applicant, leave_id=leave.pk,
                additional_start=END + timedelta(days=1),
                additional_end=END + timedelta(days=1))
        assert exc.value.code == "not_extendable"


class TestResumption:

    def test_a_normal_resumption_changes_nothing(self, applicant,
                                                  head, director):
        """BR-EL-028: no adjustment on the approved end date."""
        leave = app_service.submit(
            principal=applicant, category="EL",
            start_date=START, end_date=END)
        decision_service.unit_head_review(
            principal=head, application_id=leave.pk,
            recommendation="recommended")
        decision_service.final_sanction(
            principal=director, application_id=leave.pk,
            outcome="approve")
        record = resumption_service.submit_resumption(
            principal=applicant, leave_id=leave.pk,
            actual_resumption_date=END)
        resumption_service.review_resumption(
            principal=director, resumption_id=record.pk,
            outcome="reviewed")
        record.refresh_from_db()
        assert record.status == sm.RESUMPTION_NO_ADJUSTMENT
        assert LeaveBalance.objects.get(
            user_id=APPLICANT, category="EL").used == 2.0

    def test_an_early_resumption_restores_the_unused_portion(
            self, applicant, head, director):
        leave = app_service.submit(
            principal=applicant, category="EL",
            start_date=START, end_date=END)
        decision_service.unit_head_review(
            principal=head, application_id=leave.pk,
            recommendation="recommended")
        decision_service.final_sanction(
            principal=director, application_id=leave.pk,
            outcome="approve")
        record = resumption_service.submit_resumption(
            principal=applicant, leave_id=leave.pk,
            actual_resumption_date=END - timedelta(days=1))
        resumption_service.review_resumption(
            principal=director, resumption_id=record.pk,
            outcome="reviewed")
        leave.refresh_from_db()
        assert leave.end_date == END - timedelta(days=1)
        assert LeaveBalance.objects.get(
            user_id=APPLICANT, category="EL").used == 1.0

    def test_cl_has_no_formal_resumption(self, applicant, head):
        """BR-EL-027: resumption is for EL/COL/VL."""
        leave = app_service.submit(
            principal=applicant, category="CL",
            start_date=START, end_date=END)
        decision_service.unit_head_review(
            principal=head, application_id=leave.pk,
            outcome="approve")
        with pytest.raises(ConflictError) as exc:
            resumption_service.submit_resumption(
                principal=applicant, leave_id=leave.pk,
                actual_resumption_date=END)
        assert exc.value.code == "not_resumable"


class TestOfflineEntry:

    def test_recording_offline_leave_deducts_the_balance(
            self, org):
        """EL-UC-016: synchronisation, not a sanction."""
        admin = principal(UNIT_HEAD, ["elm.offline.record"])
        employee(APPLICANT, org=org)
        offline_service.record_offline(
            principal=admin, user_id=APPLICANT,
            category="CL", leave_year=str(START.year),
            start_date=START, end_date=END, days=2.0,
            sanction_reference="Paper/2026/014")
        balance = LeaveBalance.objects.get(
            user_id=APPLICANT, category="CL")
        assert balance.used == 2.0

    def test_evidence_is_mandatory(self, org):
        """BR-EL-029."""
        admin = principal(UNIT_HEAD, ["elm.offline.record"])
        employee(APPLICANT, org=org)
        with pytest.raises(ConflictError) as exc:
            offline_service.record_offline(
                principal=admin, user_id=APPLICANT,
                category="CL", leave_year=str(START.year),
                start_date=START, end_date=END, days=2.0,
                sanction_reference="  ")
        assert exc.value.code == "evidence_required"

    def test_an_overlapping_second_entry_is_refused(self, org):
        """The overlap check is the record-consistency guard."""
        admin = principal(UNIT_HEAD, ["elm.offline.record"])
        employee(APPLICANT, org=org)
        offline_service.record_offline(
            principal=admin, user_id=APPLICANT,
            category="CL", leave_year=str(START.year),
            start_date=START, end_date=END, days=2.0,
            sanction_reference="Paper/2026/014")
        with pytest.raises(ConflictError) as exc:
            offline_service.record_offline(
                principal=admin, user_id=APPLICANT,
                category="CL", leave_year=str(START.year),
                start_date=START + timedelta(days=1),
                end_date=END + timedelta(days=1), days=2.0,
                sanction_reference="Paper/2026/015")
        assert exc.value.code == "record_inconsistent"


class TestYearEnd:

    def test_cl_lapses_at_year_end(self, applicant, head):
        """BR-EL-002: 8 entitled, 2 used, 6 lapse."""
        app_service.submit(
            principal=applicant, category="CL",
            start_date=START, end_date=END)
        decision_service.unit_head_review(
            principal=head,
            application_id=LeaveApplication.objects.filter(
                user_id=APPLICANT, category="CL").first().pk,
            outcome="approve")
        year_end_service.run_year_end(
            leave_year=str(START.year))
        balance = LeaveBalance.objects.get(
            user_id=APPLICANT, category="CL")
        assert balance.used == 2.0
        assert balance.lapsed == 6.0
        assert balance.available == 0.0

    def test_faculty_vl_converts_to_el(self, org):
        """BR-EL-007: 2 VL : 1 EL, fractional, no VL carried."""
        year = str(START.year)
        balance = LeaveBalance.objects.create(
            user_id=FACULTY, category="VL", leave_year=year,
            entitled=60.0)
        assert balance.available == 60.0
        year_end_service.run_year_end(leave_year=year)
        # 60 VL becomes 30 EL in the following year.
        el = LeaveBalance.objects.get(
            user_id=FACULTY, category="EL",
            leave_year=str(int(year) + 1))
        assert el.opening == 30.0

    def test_el_carries_forward(self, applicant, head):
        """BR-EL-005."""
        leave = app_service.submit(
            principal=applicant, category="EL",
            start_date=START, end_date=END)
        decision_service.unit_head_review(
            principal=head, application_id=leave.pk,
            recommendation="recommended")
        director = principal(DIRECTOR, SANCTION)
        decision_service.final_sanction(
            principal=director, application_id=leave.pk,
            outcome="reject")
        year = str(START.year)
        balance = LeaveBalance.objects.get(
            user_id=APPLICANT, category="EL",
            leave_year=year)
        year_end_service.run_year_end(leave_year=year)
        next_year = LeaveBalance.objects.get(
            user_id=APPLICANT, category="EL",
            leave_year=str(int(year) + 1))
        assert next_year.opening == balance.entitled


def leave_pk():
    """The applicant's most recent leave request, for the tests
    that review the one they just created."""
    return LeaveApplication.objects.filter(
        user_id=APPLICANT).order_by("-pk").first().pk
