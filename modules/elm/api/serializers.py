"""ELM API serializers."""
from __future__ import annotations

from rest_framework import serializers

from modules.elm.models import (
    EmployeeProfile,
    Holiday,
    HolidayCalendar,
    LeaveApplication,
    LeaveBalance,
    LeaveCancellation,
    LeaveExtension,
    LeavePolicy,
    LeaveTransaction,
    Notification,
    OrgUnit,
    ResumptionRecord,
    SanctionHierarchy,
    SubstituteAssignment,
    VacationPeriod,
)


# -- Shared choice fields ---------------------------------------
# Factories, not instances: one instance cannot serve two field
# names. The choices are identical across every use, so the
# schema still names ONE component per set rather than colliding
# the categories across serializers.
def leave_category_field(**kwargs):
    return serializers.ChoiceField(
        choices=[("CL", "CL"), ("RH", "RH"), ("SCL", "SCL"),
                 ("EL", "EL"), ("COL", "COL"), ("VL", "VL")],
        **kwargs)


def employee_kind_field(**kwargs):
    return serializers.ChoiceField(
        choices=[("faculty", "Faculty"), ("staff", "Staff")],
        **kwargs)


def half_day_field(**kwargs):
    return serializers.ChoiceField(
        choices=[("", "Full day"),
                 ("first", "First half"),
                 ("second", "Second half")],
        **kwargs)


# -- Read serializers ------------------------------------------
class LeaveApplicationSerializer(serializers.ModelSerializer):
    category = leave_category_field()
    applicant_kind = employee_kind_field()
    half_day = half_day_field()

    class Meta:
        model = LeaveApplication
        fields = [
            "id", "user_id", "category",
            "start_date", "end_date",
            "half_day", "purpose",
            "leave_year", "days_requested",
            "station_leave",
            "station_leave_details",
            "substitute_required",
            "applicant_unit",
            "applicant_designation",
            "applicant_kind",
            "status", "recommendation",
            "decided_by_user_id",
            "decided_at", "decision_reason",
            "withdrawn_reason",
            "created_at", "updated_at",
        ]


class LeaveBalanceSerializer(serializers.ModelSerializer):
    category = leave_category_field()
    available = serializers.ReadOnlyField()

    class Meta:
        model = LeaveBalance
        fields = [
            "id", "user_id", "category",
            "leave_year", "entitled",
            "opening", "used", "lapsed",
            "available", "created_at",
            "updated_at",
        ]


class LeaveTransactionSerializer(serializers.ModelSerializer):
    category = leave_category_field()

    class Meta:
        model = LeaveTransaction
        fields = [
            "id", "user_id", "category",
            "leave_year", "kind", "amount",
            "reference_id",
            "reference_kind", "note",
            "created_at",
        ]


class SubstituteAssignmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubstituteAssignment
        fields = [
            "id", "kind", "application",
            "extension",
            "applicant_user_id",
            "substitute_user_id",
            "responsibility_start",
            "responsibility_end",
            "response", "responded_at",
            "decline_reason",
            "created_at", "updated_at",
        ]


class LeaveCancellationSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeaveCancellation
        fields = [
            "id", "leave", "user_id",
            "reason", "requested_on",
            "status", "decided_by_user_id",
            "decided_at", "decision_reason",
            "created_at", "updated_at",
        ]


class LeaveExtensionSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeaveExtension
        fields = [
            "id", "leave", "user_id",
            "additional_start",
            "additional_end", "purpose",
            "additional_days",
            "substitute_required",
            "status", "decided_by_user_id",
            "decided_at", "decision_reason",
            "created_at", "updated_at",
        ]


class ResumptionRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = ResumptionRecord
        fields = [
            "id", "leave", "user_id",
            "actual_resumption_date",
            "details", "submitted_at",
            "status", "reviewed_by_user_id",
            "reviewed_at", "review_note",
            "created_at", "updated_at",
        ]


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = [
            "id", "user_id", "topic",
            "subject", "body",
            "reference_kind",
            "reference_id", "created_at",
        ]


class OrgUnitSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrgUnit
        fields = [
            "id", "code", "name", "kind",
            "parent", "unit_head_user_id",
            "created_at", "updated_at",
        ]


class EmployeeProfileSerializer(serializers.ModelSerializer):
    # Named `applicant_kind`, NOT `category`: the leave category
    # owns that name, and reusing it would collapse two
    # different choice sets into one schema component.
    applicant_kind = employee_kind_field(source="category", required=False)

    class Meta:
        model = EmployeeProfile
        fields = [
            "id", "user_id", "applicant_kind",
            "designation", "unit",
            "created_at", "updated_at",
        ]


class VacationPeriodSerializer(serializers.ModelSerializer):
    class Meta:
        model = VacationPeriod
        fields = [
            "id", "academic_year", "label",
            "start_date", "end_date",
            "created_at", "updated_at",
        ]


class HolidayCalendarSerializer(serializers.ModelSerializer):
    class Meta:
        model = HolidayCalendar
        fields = [
            "id", "year", "label",
            "is_published", "published_at",
            "is_effective",
            "created_at", "updated_at",
        ]


class HolidaySerializer(serializers.ModelSerializer):
    class Meta:
        model = Holiday
        fields = [
            "id", "calendar", "date",
            "label", "is_restricted_holiday",
            "is_closed", "created_at",
            "updated_at",
        ]


class LeavePolicySerializer(serializers.ModelSerializer):
    class Meta:
        model = LeavePolicy
        fields = [
            "id", "key", "value",
            "description", "created_at",
            "updated_at",
        ]


class SanctionHierarchySerializer(serializers.ModelSerializer):
    class Meta:
        model = SanctionHierarchy
        fields = [
            "id", "category", "step_order",
            "role", "is_establishment",
            "created_at", "updated_at",
        ]


# -- Write serializers -----------------------------------------
class LeaveApplySerializer(serializers.Serializer):
    category = leave_category_field()
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    half_day = half_day_field()
    purpose = serializers.CharField(
        required=False, default="",
        allow_blank=True)
    station_leave = serializers.BooleanField(
        default=False)
    station_leave_details = serializers.CharField(
        required=False, default="",
        allow_blank=True)
    substitute_required = serializers.BooleanField(
        default=False)
    substitute_user_id = serializers.IntegerField(
        required=False, allow_null=True)


class SubstituteResponseSerializer(serializers.Serializer):
    accept = serializers.BooleanField()
    decline_reason = serializers.CharField(
        required=False, default="",
        allow_blank=True)


class ReviewSerializer(serializers.Serializer):
    outcome = serializers.ChoiceField(
        choices=[("approve", "Approve"),
                 ("reject", "Reject")],
        required=False)
    recommendation = serializers.ChoiceField(
        choices=[("recommended", "Recommended"),
                 ("not_recommended",
                  "Not Recommended")],
        required=False)
    reason = serializers.CharField(
        required=False, default="",
        allow_blank=True)


class ResumptionSerializer(serializers.Serializer):
    actual_resumption_date = serializers.DateField()
    details = serializers.CharField(
        required=False, default="",
        allow_blank=True)


class ExtensionSerializer(serializers.Serializer):
    additional_start = serializers.DateField()
    additional_end = serializers.DateField()
    purpose = serializers.CharField(
        required=False, default="",
        allow_blank=True)
    substitute_required = serializers.BooleanField(
        default=False)
    substitute_user_id = serializers.IntegerField(
        required=False, allow_null=True)


class OfflineSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    category = leave_category_field()
    leave_year = serializers.CharField()
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    days = serializers.FloatField()
    sanction_reference = serializers.CharField()
    reason_unavailable = serializers.CharField(
        required=False, default="",
        allow_blank=True)


class PolicySerializer(serializers.Serializer):
    key = serializers.CharField()
    value = serializers.CharField()
    description = serializers.CharField(
        required=False, default="",
        allow_blank=True)


class HierarchySerializer(serializers.Serializer):
    category = serializers.CharField()
    step_order = serializers.IntegerField()
    role = serializers.ChoiceField(
        choices=[
            ("unit_head", "Unit Head"),
            ("establishment",
             "Establishment (Dep. Registrar Estt.)"),
            ("deputy_registrar_estt",
             "Deputy Registrar (Estt.)"),
            ("dean", "Dean"),
            ("registrar", "Registrar"),
            ("director", "Director")])
    is_establishment = serializers.BooleanField(
        default=False)


class CalendarSerializer(serializers.Serializer):
    year = serializers.CharField()
    label = serializers.CharField()
    holidays = serializers.JSONField(
        required=False, default=list)


class SlaSerializer(serializers.Serializer):
    task_class = serializers.CharField()
    reminder = serializers.FloatField()
    escalation = serializers.FloatField()


# -- Response-only shapes for the administrative actions ----
class OfflineRecordSerializer(serializers.Serializer):
    """What a recorded retrospective entry
    confirms: the evidence, and that no
    second approval workflow was begun."""
    id = serializers.IntegerField()
    sanction_reference = serializers.CharField()
    recorded = serializers.BooleanField()


class SlaThresholds(serializers.Serializer):
    """The configured reminder and escalation
    thresholds per task class."""
    thresholds = serializers.DictField(
        child=serializers.DictField(
            child=serializers.FloatField()))


class SlaProcessResult(serializers.Serializer):
    """How many reminders and escalations
    event-triggered processing issued."""
    reminders = serializers.IntegerField()
    escalations = serializers.IntegerField()


class YearEndResult(serializers.Serializer):
    """A request to process one leaving year."""
    leave_year = serializers.CharField()


class YearEndSummary(serializers.Serializer):
    """The year-end processing summary,
    including reported exceptions."""
    leave_year = serializers.CharField()
    accounts = serializers.IntegerField()
    lapsed_days = serializers.FloatField()
    converted_vl_days = serializers.FloatField()
    carried_forward_days = serializers.FloatField()
    exceptions = serializers.ListField(
        child=serializers.CharField())
