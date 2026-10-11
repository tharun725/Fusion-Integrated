"""ELM API URLs.

Every endpoint mounts under
``/api/v1/leave/``. The module owns
its own URL namespace, so it can be
extracted into its own service later
by changing one include.
"""
from django.urls import path

from modules.elm.api import views as v

urlpatterns = [
    # employee self-service
    path("applications",
         v.MyApplicationsView.as_view(),
         name="elm-my-applications"),
    path("applications/apply",
         v.ApplyView.as_view(),
         name="elm-apply"),
    path("applications/<int:pk>",
         v.ApplicationDetailView.as_view(),
         name="elm-application"),
    path("applications/<int:pk>/withdraw",
         v.WithdrawView.as_view(),
         name="elm-withdraw"),
    path("applications/<int:pk>/export",
         v.ExportApplicationView.as_view(),
         name="elm-export-application"),
    path("applications/<int:pk>/cancel",
         v.CancellationRequestView.as_view(),
         name="elm-cancel"),
    path("applications/<int:pk>/extend",
         v.ExtensionRequestView.as_view(),
         name="elm-extend"),
    path("applications/<int:pk>/resumption",
         v.ResumptionSubmitView.as_view(),
         name="elm-resumption"),
    path("applications/<int:pk>/replacement",
         v.ReplacementView.as_view(),
         name="elm-replacement"),

    # balances and history
    path("balances",
         v.MyBalancesView.as_view(),
         name="elm-my-balances"),
    path("balances/<int:pk>",
         v.BalanceDetailView.as_view(),
         name="elm-balance"),
    path("balances/history",
         v.BalanceHistoryView.as_view(),
         name="elm-balance-history"),

    # notifications
    path("notifications",
         v.MyNotificationsView.as_view(),
         name="elm-notifications"),

    # substitute
    path("substitute-requests",
         v.MySubstituteRequestsView.as_view(),
         name="elm-substitute-requests"),
    path("substitute-requests/<int:pk>/respond",
         v.SubstituteRespondView.as_view(),
         name="elm-substitute-respond"),

    # review and sanction
    path("reviews/unit-head",
         v.UnitHeadQueueView.as_view(),
         name="elm-unit-head-queue"),
    path("applications/<int:pk>/unit-head-review",
         v.UnitHeadReviewView.as_view(),
         name="elm-unit-head-review"),
    path("reviews/establishment",
         v.EstablishmentQueueView.as_view(),
         name="elm-establishment-queue"),
    path("applications/<int:pk>/establishment-route",
         v.EstablishmentRouteView.as_view(),
         name="elm-establishment-route"),
    path("reviews/final",
         v.FinalSanctionQueueView.as_view(),
         name="elm-final-queue"),
    path("applications/<int:pk>/final-sanction",
         v.FinalSanctionView.as_view(),
         name="elm-final-sanction"),

    # cancellation
    path("cancellations/<int:pk>",
         v.CancellationDetailView.as_view(),
         name="elm-cancellation"),
    path("cancellations/<int:pk>/review",
         v.CancellationReviewView.as_view(),
         name="elm-cancellation-review"),

    # extension
    path("extensions/<int:pk>",
         v.ExtensionDetailView.as_view(),
         name="elm-extension"),
    path("extensions/<int:pk>/review",
         v.ExtensionReviewView.as_view(),
         name="elm-extension-review"),

    # resumption
    path("resumptions/<int:pk>",
         v.ResumptionDetailView.as_view(),
         name="elm-resumption"),
    path("resumptions/<int:pk>/review",
         v.ResumptionReviewView.as_view(),
         name="elm-resumption-review"),

    # administration
    path("policy",
         v.PolicyListView.as_view(),
         name="elm-policy"),
    path("hierarchy",
         v.HierarchyListView.as_view(),
         name="elm-hierarchy"),
    path("calendar",
         v.CalendarListView.as_view(),
         name="elm-calendar"),
    path("calendar/<int:pk>/publish",
         v.CalendarPublishView.as_view(),
         name="elm-calendar-publish"),
    path("calendar/holidays",
         v.HolidayListView.as_view(),
         name="elm-holidays"),
    path("offline-records",
         v.OfflineRecordView.as_view(),
         name="elm-offline-record"),
    path("records",
         v.LeaveRecordsView.as_view(),
         name="elm-records"),
    path("sla",
         v.SlaConfigView.as_view(),
         name="elm-sla"),
    path("sla/process",
         v.SlaProcessView.as_view(),
         name="elm-sla-process"),
    path("year-end",
         v.YearEndView.as_view(),
         name="elm-year-end"),
    path("org-units",
         v.OrgUnitListView.as_view(),
         name="elm-org-units"),
    path("employees",
         v.EmployeeListView.as_view(),
         name="elm-employees"),
    path("vacation-periods",
         v.VacationPeriodListView.as_view(),
         name="elm-vacation-periods"),
]
