"""ELM HTTP layer: parse, scope, delegate,
serialise.

Every read goes through a selector and
every write through a service, so
authorisation is never re-derived per
endpoint. Anything out of scope is
simply absent, which is why detail
views 404 rather than 403.
"""
from __future__ import annotations

from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.api.exceptions import NotFoundError
from fusion_auth.permissions import (
    HasModuleGrant,
    HasPermission,
)
from modules.elm.api import serializers as s
from modules.elm.domain import state_machine as sm
from modules.elm.models import (
    LeaveApplication,
    LeaveBalance,
    LeaveTransaction,
    Notification,
    SubstituteAssignment,
)
from modules.elm.selectors import scoping
from modules.elm.services import applications as application_service
from modules.elm.services import calendar as calendar_service
from modules.elm.services import cancellations as cancellation_service
from modules.elm.services import decisions as decision_service
from modules.elm.services import extensions as extension_service
from modules.elm.services import offline as offline_service
from modules.elm.services import resumptions as resumption_service
from modules.elm.services import sla as sla_service
from modules.elm.services import year_end as year_end_service

MODULE = HasModuleGrant("elm")

# Permission codes, declared in registry.py.
P_VIEW_SELF = "elm.application.view_self"
P_VIEW = "elm.application.view"
P_VIEW_UNIT = "elm.application.view_unit"
P_CREATE = "elm.application.create"
P_WITHDRAW = "elm.application.withdraw"
P_CANCEL = "elm.application.cancel_request"
P_EXTENSION = "elm.extension.request"
P_RESUME = "elm.resumption.submit"
P_EXPORT = "elm.application.export"
P_UNIT_HEAD = "elm.review.unit_head"
P_ESTABLISHMENT = "elm.review.establishment"
P_SANCTION = "elm.review.sanction"
P_BALANCE = "elm.balance.view"
P_POLICY = "elm.policy.manage"
P_CALENDAR = "elm.calendar.manage"
P_RECORD = "elm.record.manage"
P_OFFLINE = "elm.offline.record"
P_SLA = "elm.sla.manage"
P_ORG = "elm.org.manage"
P_REPORT = "elm.report.view"


def _actor(request):
    return getattr(request, "principal", None)


# -- Employee self-service -----------------------------------
class MyApplicationsView(generics.ListAPIView):
    """The caller's own leave requests,
    with status and recorded decisions
    (EL-UC-012)."""
    serializer_class = s.LeaveApplicationSerializer
    permission_classes = [MODULE,
                          HasPermission(P_VIEW_SELF)]
    queryset = LeaveApplication.objects.none()

    def get_queryset(self):
        return scoping.applications_for(
            _actor(self.request)).filter(
            user_id=_actor(self.request).user_id)


class ApplicationDetailView(generics.RetrieveAPIView):
    """One leave request, scoped so a
    foreign id is a 404."""
    serializer_class = s.LeaveApplicationSerializer
    permission_classes = [MODULE,
                          HasPermission(P_VIEW_SELF,
                                           P_VIEW,
                                           P_VIEW_UNIT)]
    queryset = LeaveApplication.objects.none()

    def get_queryset(self):
        return scoping.applications_for(
            _actor(self.request))


@extend_schema(request=s.LeaveApplySerializer,
                responses=s.LeaveApplicationSerializer)
class ApplyView(APIView):
    """Apply for leave (EL-UC-001)."""
    permission_classes = [MODULE,
                          HasPermission(P_CREATE)]

    def post(self, request):
        payload = s.LeaveApplySerializer(
            data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        application = (
            application_service.submit(
                principal=_actor(request),
                category=data["category"],
                start_date=data["start_date"],
                end_date=data["end_date"],
                half_day=data.get("half_day", ""),
                purpose=data.get("purpose", ""),
                station_leave=data.get(
                    "station_leave", False),
                station_leave_details=data.get(
                    "station_leave_details", ""),
                substitute_required=data.get(
                    "substitute_required", False),
                substitute_user_id=data.get(
                    "substitute_user_id")))
        return Response(
            s.LeaveApplicationSerializer(
                application).data,
            status=status.HTTP_201_CREATED)


@extend_schema(request=s.ReviewSerializer,
                responses=s.LeaveApplicationSerializer)
class WithdrawView(APIView):
    """Withdraw a pending request
    (EL-UC-007)."""
    permission_classes = [MODULE,
                          HasPermission(P_WITHDRAW)]

    def post(self, request, pk):
        payload = s.ReviewSerializer(
            data=request.data, partial=True)
        payload.is_valid(raise_exception=True)
        application = (
            application_service.withdraw(
                principal=_actor(request),
                application_id=pk,
                reason=payload.validated_data.get(
                    "reason", "")))
        return Response(
            s.LeaveApplicationSerializer(
                application).data)


class MyBalancesView(generics.ListAPIView):
    """The caller's current leave
    balances (EL-UC-012)."""
    serializer_class = s.LeaveBalanceSerializer
    permission_classes = [MODULE,
                          HasPermission(P_VIEW_SELF)]
    queryset = LeaveBalance.objects.none()

    def get_queryset(self):
        return scoping.balances_for(
            _actor(self.request)).filter(
            user_id=_actor(self.request).user_id)


class BalanceDetailView(generics.RetrieveAPIView):
    """One balance, scoped so a foreign
    employee is a 404 for anyone but an
    administrator."""
    serializer_class = s.LeaveBalanceSerializer
    permission_classes = [MODULE,
                          HasPermission(P_VIEW_SELF,
                                           P_BALANCE)]
    queryset = LeaveBalance.objects.none()

    def get_queryset(self):
        return scoping.balances_for(
            _actor(self.request))


class BalanceHistoryView(generics.ListAPIView):
    """The ledger for one balance."""
    serializer_class = (
        s.LeaveTransactionSerializer)
    permission_classes = [MODULE,
                          HasPermission(P_VIEW_SELF,
                                           P_BALANCE)]
    queryset = LeaveTransaction.objects.none()

    def get_queryset(self):
        return LeaveTransaction.objects.filter(
            user_id=_actor(self.request).user_id)


class MyNotificationsView(generics.ListAPIView):
    """The caller's notifications."""
    serializer_class = s.NotificationSerializer
    permission_classes = [MODULE,
                          HasPermission(P_VIEW_SELF)]
    queryset = Notification.objects.none()

    def get_queryset(self):
        return Notification.objects.filter(
            user_id=_actor(self.request).user_id)


@extend_schema(request=None,
                responses=s.LeaveApplicationSerializer)
class ExportApplicationView(APIView):
    """A printable/exportable
    representation of an accessible
    application (EL-UC-013)."""
    permission_classes = [MODULE,
                          HasPermission(P_EXPORT)]

    def get(self, request, pk):
        application = scoping.application_for(
            _actor(request), pk)
        if application is None:
            raise NotFoundError(
                "No such leave application.")
        return Response({
            "application": (
                s.LeaveApplicationSerializer(
                    application).data),
            "generated_at": (
                timezone.now().isoformat()),
            "representation": "leave-application",
        })


# -- Substitute ----------------------------------------------
class MySubstituteRequestsView(generics.ListAPIView):
    """The substitute assignments awaiting
    the caller's response (EL-UC-002)."""
    serializer_class = (
        s.SubstituteAssignmentSerializer)
    permission_classes = [MODULE,
                          HasPermission(P_VIEW_SELF)]
    queryset = SubstituteAssignment.objects.none()

    def get_queryset(self):
        return SubstituteAssignment.objects.filter(
            substitute_user_id=(
                _actor(self.request).user_id))


@extend_schema(request=s.SubstituteResponseSerializer,
                responses=s.SubstituteAssignmentSerializer)
class SubstituteRespondView(APIView):
    """Accept or decline a responsibility
    assignment (EL-UC-002)."""
    permission_classes = [MODULE,
                          HasPermission(P_VIEW_SELF)]

    def post(self, request, pk):
        payload = s.SubstituteResponseSerializer(
            data=request.data)
        payload.is_valid(raise_exception=True)
        assignment = (
            application_service
            .respond_to_substitute(
                principal=_actor(request),
                assignment_id=pk,
                accept=payload.validated_data[
                    "accept"],
                decline_reason=payload
                .validated_data.get(
                    "decline_reason", "")))
        return Response(
            s.SubstituteAssignmentSerializer(
                assignment).data)


@extend_schema(request=s.LeaveApplySerializer,
                responses=s.SubstituteAssignmentSerializer)
class ReplacementView(APIView):
    """Nominate a replacement substitute
    after a decline (EL-UC-019)."""
    permission_classes = [MODULE,
                          HasPermission(P_CREATE)]

    def post(self, request, pk):
        payload = s.LeaveApplySerializer(
            data=request.data, partial=True)
        payload.is_valid(raise_exception=True)
        assignment = (
            application_service
            .nominate_replacement(
                principal=_actor(request),
                application_id=pk,
                substitute_user_id=payload
                .validated_data.get(
                    "substitute_user_id")))
        return Response(
            s.SubstituteAssignmentSerializer(
                assignment).data,
            status=status.HTTP_201_CREATED)


# -- Review and sanction -------------------------------------
class UnitHeadQueueView(generics.ListAPIView):
    """The Unit Head's work queue."""
    serializer_class = s.LeaveApplicationSerializer
    permission_classes = [MODULE,
                          HasPermission(P_UNIT_HEAD)]
    queryset = LeaveApplication.objects.none()

    def get_queryset(self):
        return scoping.applications_for(
            _actor(self.request)).filter(
            status=sm.AWAITING_UNIT_HEAD)


@extend_schema(request=s.ReviewSerializer,
                responses=s.LeaveApplicationSerializer)
class UnitHeadReviewView(APIView):
    """Record the Unit Head's decision or
    recommendation (EL-UC-003)."""
    permission_classes = [MODULE,
                          HasPermission(P_UNIT_HEAD)]

    def post(self, request, pk):
        payload = s.ReviewSerializer(
            data=request.data)
        payload.is_valid(raise_exception=True)
        application = (
            decision_service.unit_head_review(
                principal=_actor(request),
                application_id=pk,
                outcome=payload.validated_data.get(
                    "outcome", ""),
                recommendation=payload
                .validated_data.get(
                    "recommendation", ""),
                reason=payload.validated_data.get(
                    "reason", "")))
        return Response(
            s.LeaveApplicationSerializer(
                application).data)


class EstablishmentQueueView(generics.ListAPIView):
    """The Establishment processing
    queue."""
    serializer_class = s.LeaveApplicationSerializer
    permission_classes = [MODULE,
                          HasPermission(P_ESTABLISHMENT)]
    queryset = LeaveApplication.objects.none()

    def get_queryset(self):
        return scoping.applications_for(
            _actor(self.request)).filter(
            status=sm.AWAITING_ESTABLISHMENT)


@extend_schema(request=None,
                responses=s.LeaveApplicationSerializer)
class EstablishmentRouteView(APIView):
    """Verify and route a higher-sanction
    request (EL-UC-004)."""
    permission_classes = [MODULE,
                          HasPermission(P_ESTABLISHMENT)]

    def post(self, request, pk):
        application = (
            decision_service.establishment_route(
                principal=_actor(request),
                application_id=pk))
        return Response(
            s.LeaveApplicationSerializer(
                application).data)


class FinalSanctionQueueView(generics.ListAPIView):
    """The final sanctioning
    authority's queue."""
    serializer_class = s.LeaveApplicationSerializer
    permission_classes = [MODULE,
                          HasPermission(P_SANCTION)]
    queryset = LeaveApplication.objects.none()

    def get_queryset(self):
        return scoping.applications_for(
            _actor(self.request)).filter(
            status__in=(
                sm.AWAITING_FINAL, sm.AWAITING_DIRECTOR))


@extend_schema(request=s.ReviewSerializer,
                responses=s.LeaveApplicationSerializer)
class FinalSanctionView(APIView):
    """Record the final sanctioning
    decision (EL-UC-005)."""
    permission_classes = [MODULE,
                          HasPermission(P_SANCTION)]

    def post(self, request, pk):
        payload = s.ReviewSerializer(
            data=request.data)
        payload.is_valid(raise_exception=True)
        application = (
            decision_service.final_sanction(
                principal=_actor(request),
                application_id=pk,
                outcome=payload.validated_data.get(
                    "outcome", ""),
                reason=payload.validated_data.get(
                    "reason", "")))
        return Response(
            s.LeaveApplicationSerializer(
                application).data)


# -- Cancellation --------------------------------------------
@extend_schema(request=s.ReviewSerializer,
                responses=s.LeaveCancellationSerializer)
class CancellationRequestView(APIView):
    """Request cancellation of an
    approved leave (EL-UC-008)."""
    permission_classes = [MODULE,
                          HasPermission(P_CANCEL)]

    def post(self, request, pk):
        payload = s.ReviewSerializer(
            data=request.data, partial=True)
        payload.is_valid(raise_exception=True)
        cancellation = (
            cancellation_service
            .request_cancellation(
                principal=_actor(request),
                leave_id=pk,
                reason=payload.validated_data.get(
                    "reason", "")))
        return Response(
            s.LeaveCancellationSerializer(
                cancellation).data,
            status=status.HTTP_201_CREATED)


@extend_schema(request=s.ReviewSerializer,
                responses=s.LeaveCancellationSerializer)
class CancellationReviewView(APIView):
    """Decide a cancellation at whatever
    stage it has reached."""
    permission_classes = [MODULE,
                          HasPermission(P_UNIT_HEAD,
                                           P_ESTABLISHMENT,
                                           P_SANCTION)]

    def post(self, request, pk):
        payload = s.ReviewSerializer(
            data=request.data)
        payload.is_valid(raise_exception=True)
        cancellation = (
            cancellation_service
            .cancellation_review(
                principal=_actor(request),
                cancellation_id=pk,
                outcome=payload.validated_data.get(
                    "outcome", ""),
                recommendation=payload
                .validated_data.get(
                    "recommendation", ""),
                reason=payload.validated_data.get(
                    "reason", "")))
        return Response(
            s.LeaveCancellationSerializer(
                cancellation).data)


class CancellationDetailView(generics.RetrieveAPIView):
    serializer_class = (
        s.LeaveCancellationSerializer)
    permission_classes = [MODULE,
                          HasPermission(P_VIEW,
                                           P_VIEW_UNIT)]

    def get_queryset(self):
        from modules.elm.models import LeaveCancellation
        return (LeaveCancellation.objects
                .select_related("leave"))


# -- Extension -----------------------------------------------
@extend_schema(request=s.ExtensionSerializer,
                responses=s.LeaveExtensionSerializer)
class ExtensionRequestView(APIView):
    """Request an extension of ongoing
    leave (EL-UC-009)."""
    permission_classes = [MODULE,
                          HasPermission(P_EXTENSION)]

    def post(self, request, pk):
        payload = s.ExtensionSerializer(
            data=request.data)
        payload.is_valid(raise_exception=True)
        extension = (
            extension_service.request_extension(
                principal=_actor(request),
                leave_id=pk,
                additional_start=payload
                .validated_data["additional_start"],
                additional_end=payload
                .validated_data["additional_end"],
                purpose=payload.validated_data.get(
                    "purpose", ""),
                substitute_required=payload
                .validated_data.get(
                    "substitute_required", False),
                substitute_user_id=payload
                .validated_data.get(
                    "substitute_user_id")))
        return Response(
            s.LeaveExtensionSerializer(
                extension).data,
            status=status.HTTP_201_CREATED)


@extend_schema(request=s.ReviewSerializer,
                responses=s.LeaveExtensionSerializer)
class ExtensionReviewView(APIView):
    """Decide an extension at whatever
    stage it has reached."""
    permission_classes = [MODULE,
                          HasPermission(P_UNIT_HEAD,
                                           P_ESTABLISHMENT,
                                           P_SANCTION)]

    def post(self, request, pk):
        payload = s.ReviewSerializer(
            data=request.data)
        payload.is_valid(raise_exception=True)
        extension = (
            extension_service.extension_review(
                principal=_actor(request),
                extension_id=pk,
                outcome=payload.validated_data.get(
                    "outcome", ""),
                recommendation=payload
                .validated_data.get(
                    "recommendation", ""),
                reason=payload.validated_data.get(
                    "reason", "")))
        return Response(
            s.LeaveExtensionSerializer(
                extension).data)


class ExtensionDetailView(generics.RetrieveAPIView):
    serializer_class = s.LeaveExtensionSerializer
    permission_classes = [MODULE,
                          HasPermission(P_VIEW,
                                           P_VIEW_UNIT)]

    def get_queryset(self):
        from modules.elm.models import LeaveExtension
        return (LeaveExtension.objects
                .select_related("leave"))


# -- Resumption ----------------------------------------------
@extend_schema(request=s.ResumptionSerializer,
                responses=s.ResumptionRecordSerializer)
class ResumptionSubmitView(APIView):
    """Submit actual resumption of duty
    (EL-UC-010)."""
    permission_classes = [MODULE,
                          HasPermission(P_RESUME)]

    def post(self, request, pk):
        payload = s.ResumptionSerializer(
            data=request.data)
        payload.is_valid(raise_exception=True)
        record = (
            resumption_service.submit_resumption(
                principal=_actor(request),
                leave_id=pk,
                actual_resumption_date=payload
                .validated_data[
                    "actual_resumption_date"],
                details=payload.validated_data.get(
                    "details", "")))
        return Response(
            s.ResumptionRecordSerializer(
                record).data,
            status=status.HTTP_201_CREATED)


@extend_schema(request=s.ReviewSerializer,
                responses=s.ResumptionRecordSerializer)
class ResumptionReviewView(APIView):
    """Review a submitted resumption
    (EL-UC-011)."""
    permission_classes = [MODULE,
                          HasPermission(P_SANCTION)]

    def post(self, request, pk):
        payload = s.ReviewSerializer(
            data=request.data, partial=True)
        payload.is_valid(raise_exception=True)
        record = (
            resumption_service.review_resumption(
                principal=_actor(request),
                resumption_id=pk,
                outcome=payload.validated_data.get(
                    "outcome", ""),
                note=payload.validated_data.get(
                    "reason", "")))
        return Response(
            s.ResumptionRecordSerializer(
                record).data)


class ResumptionDetailView(generics.RetrieveAPIView):
    serializer_class = s.ResumptionRecordSerializer
    permission_classes = [MODULE,
                          HasPermission(P_VIEW,
                                           P_VIEW_UNIT)]

    def get_queryset(self):
        from modules.elm.models import ResumptionRecord
        return (ResumptionRecord.objects
                .select_related("leave"))


# -- Administration ----------------------------------------
class PolicyListView(generics.ListCreateAPIView):
    """Maintain current policy parameters
    (EL-UC-014)."""
    serializer_class = s.LeavePolicySerializer
    permission_classes = [MODULE,
                          HasPermission(P_POLICY)]

    def get_queryset(self):
        from modules.elm.models import LeavePolicy
        return LeavePolicy.objects.all()

    def create(self, request):
        payload = s.PolicySerializer(
            data=request.data)
        payload.is_valid(raise_exception=True)
        from modules.elm.services import config
        policy = config.set_policy(
            key=payload.validated_data["key"],
            value=payload.validated_data["value"],
            description=payload.validated_data.get(
                "description", ""),
            actor=_actor(request))
        return Response(
            s.LeavePolicySerializer(policy).data,
            status=status.HTTP_201_CREATED)


class HierarchyListView(generics.ListCreateAPIView):
    """Maintain the sanction hierarchy
    (EL-UC-014)."""
    serializer_class = (
        s.SanctionHierarchySerializer)
    permission_classes = [MODULE,
                          HasPermission(P_POLICY)]

    def get_queryset(self):
        from modules.elm.models import SanctionHierarchy
        return SanctionHierarchy.objects.all()

    def create(self, request):
        payload = s.HierarchySerializer(
            data=request.data)
        payload.is_valid(raise_exception=True)
        hierarchy = _upsert_hierarchy_step(
            payload.validated_data)
        return Response(
            s.SanctionHierarchySerializer(
                hierarchy).data,
            status=status.HTTP_201_CREATED)


def _upsert_hierarchy_step(validated) -> object:
    """Create or revise one configured
    sanctioning step (EL-UC-014)."""
    from modules.elm.models import SanctionHierarchy
    hierarchy, _ = (
        SanctionHierarchy.objects
        .update_or_create(
            category=validated["category"],
            step_order=validated["step_order"],
            defaults={
                "role": validated["role"],
                "is_establishment":
                    validated.get(
                        "is_establishment", False),
            }))
    return hierarchy


class CalendarListView(generics.ListCreateAPIView):
    """Create and revise the holiday/RH
    calendar (EL-UC-015)."""
    serializer_class = (
        s.HolidayCalendarSerializer)
    permission_classes = [MODULE,
                          HasPermission(P_CALENDAR)]

    def get_queryset(self):
        from modules.elm.models import HolidayCalendar
        return HolidayCalendar.objects.all()

    def create(self, request):
        payload = s.CalendarSerializer(
            data=request.data)
        payload.is_valid(raise_exception=True)
        calendar = calendar_service.create_calendar(
            year=payload.validated_data["year"],
            label=payload.validated_data["label"],
            holidays=payload.validated_data.get(
                "holidays", []),
            actor=_actor(request))
        return Response(
            s.HolidayCalendarSerializer(
                calendar).data,
            status=status.HTTP_201_CREATED)


@extend_schema(request=s.HolidayCalendarSerializer,
                responses=s.HolidayCalendarSerializer)
class CalendarPublishView(APIView):
    """Publish a replacement calendar,
    making it effective (EL-UC-015)."""
    permission_classes = [MODULE,
                          HasPermission(P_CALENDAR)]

    def post(self, request, pk):
        calendar = calendar_service.publish(
            calendar_id=pk,
            actor=_actor(request))
        return Response(
            s.HolidayCalendarSerializer(
                calendar).data)


class HolidayListView(generics.ListAPIView):
    """The days of a calendar."""
    serializer_class = s.HolidaySerializer
    permission_classes = [MODULE,
                          HasPermission(P_CALENDAR)]

    def get_queryset(self):
        from modules.elm.models import Holiday
        return Holiday.objects.all()


@extend_schema(request=s.OfflineSerializer,
                responses=s.OfflineRecordSerializer)
class OfflineRecordView(APIView):
    """Record already-sanctioned offline
    leave (EL-UC-016)."""
    permission_classes = [MODULE,
                          HasPermission(P_OFFLINE)]

    def post(self, request):
        payload = s.OfflineSerializer(
            data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        record = offline_service.record_offline(
            principal=_actor(request),
            user_id=data["user_id"],
            category=data["category"],
            leave_year=data["leave_year"],
            start_date=data["start_date"],
            end_date=data["end_date"],
            days=data["days"],
            sanction_reference=data[
                "sanction_reference"],
            reason_unavailable=data.get(
                "reason_unavailable", ""))
        return Response({
            "id": record.pk,
            "sanction_reference": (
                record.sanction_reference),
            "recorded": True,
        }, status=status.HTTP_201_CREATED)


class LeaveRecordsView(generics.ListAPIView):
    """Authorised leave-record maintenance
    (EL-UC-017)."""
    serializer_class = s.LeaveApplicationSerializer
    permission_classes = [MODULE,
                          HasPermission(P_RECORD)]
    queryset = LeaveApplication.objects.none()

    def get_queryset(self):
        return scoping.applications_for(
            _actor(self.request))


@extend_schema(request=s.SlaSerializer, responses=s.SlaThresholds)
class SlaConfigView(APIView):
    """Configure SLA thresholds
    (EL-UC-018), and trigger event
    processing (EL-UC-021)."""
    permission_classes = [MODULE,
                          HasPermission(P_SLA)]

    def get(self, request):
        from modules.elm.services import config
        return Response(
            config.sla_thresholds())

    def post(self, request):
        payload = s.SlaSerializer(
            data=request.data)
        payload.is_valid(raise_exception=True)
        from modules.elm.services import config
        config.set_sla_threshold(
            task_class=payload.validated_data[
                "task_class"],
            reminder=payload.validated_data[
                "reminder"],
            escalation=payload.validated_data[
                "escalation"],
            actor=_actor(request))
        return Response(
            config.sla_thresholds())


@extend_schema(request=None, responses=s.SlaProcessResult)
class SlaProcessView(APIView):
    """Run event-triggered SLA
    processing (EL-UC-021)."""
    permission_classes = [MODULE,
                          HasPermission(P_SLA)]

    def post(self, request):
        result = sla_service.process_thresholds(
            task_class=request.data.get(
                "task_class"))
        return Response(result)


@extend_schema(request=s.YearEndResult,
                responses=s.YearEndSummary)
class YearEndView(APIView):
    """Execute year-end leave processing
    (EL-UC-020)."""
    permission_classes = [MODULE,
                          HasPermission(P_SLA)]

    def post(self, request):
        leave_year = request.data.get(
            "leave_year",
            str(timezone.now().year))
        result = year_end_service.run_year_end(
            leave_year=leave_year)
        return Response(result)


class OrgUnitListView(generics.ListCreateAPIView):
    """Maintain organisational units
    (EL-UC-014)."""
    serializer_class = s.OrgUnitSerializer
    permission_classes = [MODULE,
                          HasPermission(P_ORG)]

    def get_queryset(self):
        from modules.elm.models import OrgUnit
        return OrgUnit.objects.all()

    def create(self, request):
        payload = s.OrgUnitSerializer(
            data=request.data)
        payload.is_valid(raise_exception=True)
        unit = payload.save()
        return Response(
            s.OrgUnitSerializer(unit).data,
            status=status.HTTP_201_CREATED)


class EmployeeListView(generics.ListAPIView):
    """The employee directory ELM
    routes against."""
    serializer_class = (
        s.EmployeeProfileSerializer)
    permission_classes = [MODULE,
                          HasPermission(P_VIEW,
                                           P_VIEW_UNIT)]

    def get_queryset(self):
        from modules.elm.models import EmployeeProfile
        return EmployeeProfile.objects.all()


class VacationPeriodListView(generics.ListAPIView):
    """The vacation periods VL is availed
    in ??" the projection of the Academic
    Calendar (EXT-01)."""
    serializer_class = (
        s.VacationPeriodSerializer)
    permission_classes = [MODULE,
                          HasPermission(P_VIEW,
                                           P_VIEW_UNIT)]

    def get_queryset(self):
        from modules.elm.models import VacationPeriod
        return VacationPeriod.objects.all()
