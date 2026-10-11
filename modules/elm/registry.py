"""What the server tells the shell about this module (ADR-0010).

Nav items carry `required_permission` and the server filters
before sending -- the client does zero filtering, so a link a
role cannot use never reaches the browser at all.
"""
MODULE = {
    "code": "elm",
    "label": "Employee Leave Management",
    "icon": "CalendarClock",
    "base_path": "/leave",
    "nav_section": "HR",
    "sort_order": 20,
    "status": "active",
}

NAV_ITEMS = [
    # -- employee: own leave first -----------------------------
    {"code": "elm.mine", "label": "My Leave",
     "icon": "CalendarHeart", "to": "/leave/mine",
     "required_permission": "elm.application.view_self",
     "sort_order": 5},
    {"code": "elm.apply", "label": "Apply for Leave",
     "icon": "CalendarPlus", "to": "/leave/apply",
     "required_permission": "elm.application.create",
     "sort_order": 10},
    {"code": "elm.balances", "label": "My Balances",
     "icon": "Scale", "to": "/leave/balances",
     "required_permission": "elm.application.view_self",
     "sort_order": 15},
    {"code": "elm.notifications", "label": "Notifications",
     "icon": "Bell", "to": "/leave/notifications",
     "required_permission": "elm.application.view_self",
     "sort_order": 20},

    # -- review and sanction ---------------------------------
    {"code": "elm.queue", "label": "Review Queue",
     "icon": "Inbox", "to": "/leave/queue",
     "required_permission": "elm.review.unit_head",
     "sort_order": 40},
    {"code": "elm.sanctions", "label": "Sanction Queue",
     "icon": "Stamp", "to": "/leave/sanctions",
     "required_permission": "elm.review.sanction",
     "sort_order": 45},

    # -- administration --------------------------------------
    {"code": "elm.policy", "label": "Policy & Hierarchy",
     "icon": "Settings", "to": "/leave/policy",
     "required_permission": "elm.policy.manage",
     "sort_order": 60},
    {"code": "elm.calendar", "label": "Holiday Calendar",
     "icon": "CalendarDays", "to": "/leave/calendar",
     "required_permission": "elm.calendar.manage",
     "sort_order": 65},
    {"code": "elm.reports", "label": "Reports",
     "icon": "ChartBar", "to": "/leave/reports",
     "required_permission": "elm.report.view",
     "sort_order": 70},
]

#: Every permission this module recognises; ROLE_GRANTS below
#: says who holds each.
PERMISSIONS = [
    ("elm.application.view_self",
     "See one's own leave requests and balances"),
    ("elm.application.view",
     "See all leave requests"),
    ("elm.application.view_unit",
     "See one's unit's leave requests"),
    ("elm.application.create",
     "Apply for leave"),
    ("elm.application.withdraw",
     "Withdraw a pending request"),
    ("elm.application.cancel_request",
     "Request cancellation of approved leave"),
    ("elm.extension.request",
     "Request an extension of ongoing leave"),
    ("elm.resumption.submit",
     "Submit resumption of duty"),
    ("elm.application.export",
     "Export a leave application"),
    ("elm.review.unit_head",
     "Review and recommend at Unit Head"),
    ("elm.review.establishment",
     "Verify and route at Establishment"),
    ("elm.review.sanction",
     "Make the final sanctioning decision"),
    ("elm.balance.view",
     "See every employee's leave balances"),
    ("elm.policy.manage",
     "Maintain policy and hierarchy configuration"),
    ("elm.calendar.manage",
     "Maintain and publish the holiday/RH calendar"),
    ("elm.record.manage",
     "Maintain authorized leave records"),
    ("elm.offline.record",
     "Record already-sanctioned offline leave"),
    ("elm.sla.manage",
     "Configure workflow SLA thresholds"),
    ("elm.org.manage",
     "Maintain organisational units"),
    ("elm.report.view",
     "See leave reports"),
]

#: Performed by a service or a scheduled task, so no
#: designation holds them.
SYSTEM_PERMISSIONS = [
    "elm.system.year_end",
    "elm.system.sla_process",
]

# -- Per-designation grants ----------------------------------
#: Any faculty or staff member: their own leave activity.
_EMPLOYEE = [
    "elm.application.view_self",
    "elm.application.create",
    "elm.application.withdraw",
    "elm.application.cancel_request",
    "elm.extension.request",
    "elm.resumption.submit",
    "elm.application.export",
]

#: A Unit Head: their own leave, plus their unit's review
#: queue.
_UNIT_HEAD = [
    *_EMPLOYEE,
    "elm.application.view_unit",
    "elm.review.unit_head",
]

#: The Establishment processing role (Deputy Registrar Estt.).
_ESTABLISHMENT = [
    "elm.application.view",
    "elm.application.view_unit",
    "elm.review.establishment",
]

#: A competent sanctioning authority: Dean, Registrar,
#: Director. The Director also holds the employee grants,
#: because the Director's own leave self-sanctions.
_AUTHORITY = [
    *_EMPLOYEE,
    "elm.application.view",
    "elm.review.sanction",
]

#: The Leave Administrator: configuration, calendar, records
#: and offline entry, over the whole module.
_LEAVE_ADMIN = [
    "elm.application.view",
    "elm.application.view_unit",
    "elm.balance.view",
    "elm.policy.manage",
    "elm.calendar.manage",
    "elm.record.manage",
    "elm.offline.record",
    "elm.sla.manage",
    "elm.org.manage",
    "elm.report.view",
]

#: Keyed by the designation/role name as the IAM grants it.
ROLE_GRANTS = {
    "employee": _EMPLOYEE,
    "unit_head": _UNIT_HEAD,
    "establishment_officer": _ESTABLISHMENT,
    "deputy_registrar_estt": _ESTABLISHMENT,
    "dean": _AUTHORITY,
    "registrar": _AUTHORITY,
    "director": _AUTHORITY,
    "leave_admin": _LEAVE_ADMIN,
}
