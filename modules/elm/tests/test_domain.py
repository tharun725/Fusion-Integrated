"""ELM domain tests: pure Python, no database, milliseconds.

These cover the rules ELM encodes -- entitlements, counting,
the state machines and the validators -- which is exactly
the layer CI keeps free of Django.
"""
from datetime import date

import pytest

from modules.elm.domain import entitlements as ent
from modules.elm.domain import state_machine as sm
from modules.elm.domain import validation as rules

MON = date(2026, 8, 3)      # a Monday
TUE = date(2026, 8, 4)      # the day after


# ---- entitlements (BR-EL-002..009) -------------------------------------
class TestEntitlements:

    def test_casual_leave_is_eight_and_lapses(self):
        assert ent.default_entitlement("CL", is_faculty=False) == 8
        assert ent.lapses_at_year_end("CL")
        assert not ent.carries_forward("CL")

    def test_restricted_holiday_is_two_and_lapses(self):
        assert ent.default_entitlement("RH", is_faculty=False) == 2
        assert ent.lapses_at_year_end("RH")

    def test_scl_is_fifteen_and_lapses(self):
        assert ent.default_entitlement("SCL", is_faculty=False) == 15
        assert ent.lapses_at_year_end("SCL")

    def test_non_faculty_gets_thirty_el_and_carries_forward(self):
        assert ent.default_entitlement("EL", is_faculty=False) == 30
        assert ent.carries_forward("EL")

    def test_faculty_get_sixty_vl_and_no_direct_el(self):
        """Faculty earn EL from VL conversion, not a direct grant."""
        assert ent.default_entitlement("VL", is_faculty=True) == 60
        assert ent.default_entitlement("EL", is_faculty=True) == 0

    def test_col_is_twenty_and_carries_forward(self):
        assert ent.default_entitlement("COL", is_faculty=False) == 20
        assert ent.carries_forward("COL")

    def test_vl_does_not_carry_forward(self):
        assert not ent.carries_forward("VL")

    def test_only_the_six_supported_categories(self):
        assert set(ent.CATEGORIES) == {
            "CL", "RH", "SCL", "EL", "COL", "VL"}


# ---- counting (BR-EL-010, BR-EL-011) ----------------------------------
class TestCounting:

    def test_el_counts_every_calendar_day(self):
        """A Friday-to-Monday EL is 4 days, not 2: weekends inside a
        continuous interval count (BR-EL-011)."""
        assert ent.count_leave_days(
            "EL", date(2026, 8, 7), date(2026, 8, 10)) == 4.0

    def test_col_and_vl_count_continuously_too(self):
        assert ent.count_leave_days(
            "COL", date(2026, 8, 7), date(2026, 8, 9)) == 3.0
        assert ent.count_leave_days(
            "VL", date(2026, 8, 7), date(2026, 8, 9)) == 3.0

    def test_cl_skips_weekends(self):
        """Friday to Monday is 2 working days for CL."""
        assert ent.count_leave_days(
            "CL", date(2026, 8, 7), date(2026, 8, 10)) == 2.0

    def test_cl_skips_closed_holidays(self):
        closed = frozenset({MON})
        assert ent.count_leave_days(
            "CL", MON, MON, closed_holidays=closed) == 0.0

    def test_closed_holiday_does_not_reduce_a_continuous_interval(self):
        """A weekend closure is irrelevant to a continuous count."""
        closed = frozenset({date(2026, 8, 8),
                            date(2026, 8, 9)})
        assert ent.count_leave_days(
            "EL", date(2026, 8, 7), date(2026, 8, 10),
            closed_holidays=closed) == 4.0

    def test_a_half_day_cl_consumes_exactly_half(self):
        assert ent.count_leave_days(
            "CL", MON, MON, half_day="first") == 0.5
        assert ent.count_leave_days(
            "CL", MON, MON, half_day="second") == 0.5

    def test_only_cl_may_be_a_half_day(self):
        with pytest.raises(ValueError):
            ent.count_leave_days("EL", MON, MON,
                                 half_day="first")

    def test_end_before_start_is_a_value_error(self):
        with pytest.raises(ValueError):
            ent.count_leave_days("CL", MON, date(2026, 8, 1))


# ---- year-end VL conversion (BR-EL-007) -------------------------------
class TestYearEndConversion:

    def test_two_vl_becomes_one_el(self):
        assert ent.vl_to_el(2.0) == 1.0

    def test_fractional_vl_converts_fractionally(self):
        assert ent.vl_to_el(2.5) == 1.25
        assert ent.vl_to_el(1.0) == 0.5

    def test_unused_vl_converts_completely(self):
        assert ent.vl_to_el(60.0) == 30.0


# ---- validation (BR-EL-001, 003, 006, 012, 014) -----------------------
class TestValidation:

    def test_only_supported_categories_pass(self):
        assert rules.is_supported_category("EL")
        assert not rules.is_supported_category("ML")

    def test_first_and_second_cl_halves_do_not_overlap(self):
        """BR-EL-012: the same date in different halves is fine."""
        assert rules.find_overlap(
            MON, MON, half_day="second",
            existing=[(MON, MON, "first")]) is None

    def test_two_first_halves_on_the_same_date_overlap(self):
        clash = rules.find_overlap(
            MON, MON, half_day="first",
            existing=[(MON, MON, "first")])
        assert clash is not None

    def test_overlapping_intervals_are_refused(self):
        clash = rules.find_overlap(
            MON, date(2026, 8, 12),
            existing=[(date(2026, 8, 10),
                       date(2026, 8, 14), "")])
        assert clash is not None

    def test_adjacent_intervals_do_not_overlap(self):
        assert rules.find_overlap(
            date(2026, 8, 10), date(2026, 8, 12),
            existing=[(date(2026, 8, 13),
                       date(2026, 8, 14), "")]) is None

    def test_rh_must_land_on_a_restricted_holiday(self):
        rh = frozenset({MON})
        assert rules.rh_dates_are_applicable(
            MON, MON, restricted_holidays=rh) == []

    def test_rh_on_an_ordinary_day_reports_that_day(self):
        missing = rules.rh_dates_are_applicable(
            MON, TUE, restricted_holidays=frozenset({MON}))
        assert missing == [TUE]

    def test_vl_must_fall_inside_one_vacation_period(self):
        periods = [(date(2026, 12, 1), date(2026, 12, 31))]
        assert rules.period_within_vacation(
            date(2026, 12, 5), date(2026, 12, 10),
            vacation_periods=periods)
        assert not rules.period_within_vacation(
            date(2026, 12, 5), date(2027, 1, 10),
            vacation_periods=periods)

    def test_a_substitute_must_be_another_employee(self):
        base = {
            "applicant_user_id": 1, "is_employee": True,
            "responsibility_start": MON,
            "responsibility_end": MON,
            "substitute_leave": [],
        }
        assert rules.substitute_is_eligible(
            substitute_user_id=2, **base)
        assert not rules.substitute_is_eligible(
            substitute_user_id=1, **base)

    def test_a_non_employee_cannot_be_a_substitute(self):
        assert not rules.substitute_is_eligible(
            applicant_user_id=1, substitute_user_id=2,
            is_employee=False, responsibility_start=MON,
            responsibility_end=MON, substitute_leave=[])

    def test_a_substitute_with_overlapping_leave_is_refused(self):
        base = {
            "applicant_user_id": 1,
            "substitute_user_id": 2,
            "is_employee": True,
            "responsibility_start": MON,
            "responsibility_end": MON,
        }
        assert rules.substitute_is_eligible(**base,
            substitute_leave=[])
        assert not rules.substitute_is_eligible(**base,
            substitute_leave=[(date(2026, 8, 1),
                               date(2026, 8, 20))])

    def test_a_substitute_whose_leave_does_not_reach_is_fine(self):
        base = {
            "applicant_user_id": 1,
            "substitute_user_id": 2,
            "is_employee": True,
            "responsibility_start": MON,
            "responsibility_end": MON,
        }
        assert rules.substitute_is_eligible(**base,
            substitute_leave=[(date(2026, 8, 25),
                               date(2026, 8, 31))])


# ---- the leave state machine ------------------------------------------
ALL_LEAVE = [
    sm.DRAFT, sm.AWAITING_SUBSTITUTE, sm.APPLICANT_ACTION,
    sm.AWAITING_UNIT_HEAD, sm.AWAITING_ESTABLISHMENT,
    sm.AWAITING_FINAL, sm.AWAITING_DIRECTOR, sm.APPROVED,
    sm.REJECTED, sm.WITHDRAWN, sm.ONGOING, sm.CANCELLED,
]


class TestLeaveStateMachine:

    def test_the_table_is_the_specification(self):
        """Exhaustive matrix: legal iff present in the table."""
        declared = {(t.frm, t.to)
                    for t in sm.NEW_LEAVE_TRANSITIONS}
        for frm in ALL_LEAVE:
            for to in ALL_LEAVE:
                assert sm.is_legal_transition(
                    "leave", frm, to) == ((frm, to) in declared)

    def test_approved_leave_can_become_ongoing(self):
        assert sm.is_legal_transition(
            "leave", sm.APPROVED, sm.ONGOING)

    def test_a_terminal_state_has_no_exit(self):
        for state in (sm.REJECTED, sm.WITHDRAWN, sm.CANCELLED):
            assert sm.allowed_targets_for(
                "leave", state) == []

    def test_withdrawal_is_available_from_every_pending_state(self):
        """BR-EL-022: a pending request may be withdrawn at any
        time before final approval."""
        for state in sm.PENDING_STATES:
            assert sm.is_legal_transition(
                "leave", state, sm.WITHDRAWN)

    def test_an_approved_leave_can_no_longer_be_withdrawn(self):
        assert not sm.is_legal_transition(
            "leave", sm.APPROVED, sm.WITHDRAWN)

    def test_submission_without_a_substitute_goes_to_the_unit_head(self):
        assert sm.is_legal_transition(
            "leave", sm.DRAFT, sm.AWAITING_UNIT_HEAD)

    def test_submission_with_a_substitute_waits_for_consent(self):
        """BR-EL-015: routing waits on the consent gate."""
        assert sm.is_legal_transition(
            "leave", sm.DRAFT, sm.AWAITING_SUBSTITUTE)

    def test_a_declined_substitute_holds_the_gate_closed(self):
        assert sm.is_legal_transition(
            "leave", sm.AWAITING_SUBSTITUTE,
            sm.APPLICANT_ACTION)
        assert not sm.is_legal_transition(
            "leave", sm.APPLICANT_ACTION, sm.AWAITING_UNIT_HEAD)

    def test_only_a_replacement_reopens_the_gate(self):
        assert sm.is_legal_transition(
            "leave", sm.APPLICANT_ACTION, sm.AWAITING_SUBSTITUTE)

    def test_a_director_leave_skips_the_unit_head(self):
        """BR-EL-020: the self-sanction path replaces the normal
        route."""
        assert sm.is_legal_transition(
            "leave", sm.DRAFT, sm.AWAITING_DIRECTOR)
        assert sm.is_legal_transition(
            "leave", sm.AWAITING_DIRECTOR, sm.APPROVED)

    def test_an_employee_cannot_record_their_own_sanction(self):
        """The final decision belongs to an authority, not the
        applicant."""
        with pytest.raises(sm.ActorNotAllowed):
            sm.resolve_transition(
                "leave", sm.AWAITING_FINAL, sm.APPROVED,
                sm.EMPLOYEE)

    def test_an_illegal_transition_raises(self):
        with pytest.raises(sm.InvalidTransition):
            sm.resolve_transition(
                "leave", sm.DRAFT, sm.APPROVED)


class TestCancellationMachine:

    def test_cl_rh_cancellation_is_decided_at_the_unit_head(self):
        assert sm.is_legal_transition(
            "cancellation", sm.CANCEL_PENDING_UH,
            sm.CANCEL_APPROVED)

    def test_a_higher_sanction_cancellation_needs_a_final_decision(self):
        assert sm.is_legal_transition(
            "cancellation", sm.CANCEL_PENDING_UH,
            sm.CANCEL_PENDING_FINAL)
        assert sm.is_legal_transition(
            "cancellation", sm.CANCEL_PENDING_FINAL,
            sm.CANCEL_APPROVED)

    def test_a_decided_cancellation_is_terminal(self):
        assert sm.allowed_targets_for(
            "cancellation", sm.CANCEL_APPROVED) == []


class TestExtensionMachine:

    def test_an_extension_waits_on_the_unit_head(self):
        assert sm.is_legal_transition(
            "extension", sm.EXT_AWAITING_UNIT_HEAD,
            sm.EXT_PENDING_FINAL)

    def test_an_approved_extension_is_terminal(self):
        assert sm.allowed_targets_for(
            "extension", sm.EXT_APPROVED) == []

    def test_a_pending_extension_may_be_withdrawn_as_a_rejection(self):
        for state in sm.EXTENSION_PENDING_STATES:
            assert sm.is_legal_transition(
                "extension", state, sm.EXT_REJECTED)


class TestResumptionMachine:

    def test_a_matching_date_changes_nothing(self):
        assert sm.is_legal_transition(
            "resumption", sm.RESUMPTION_PENDING,
            sm.RESUMPTION_NO_ADJUSTMENT)

    def test_a_different_date_triggers_the_adjusted_branch(self):
        assert sm.is_legal_transition(
            "resumption", sm.RESUMPTION_PENDING,
            sm.RESUMPTION_ADJUSTED)

    def test_a_reviewed_resumption_is_terminal(self):
        """No generic 'Closed' state is created."""
        assert sm.allowed_targets_for(
            "resumption", sm.RESUMPTION_NO_ADJUSTMENT) == []
