"""ELM models -- the module's own tables.

People are referenced by plain ``user_id`` integers, never
foreign keys: this database has no user table, and a cross-boundary
reference must stay unconstrained so the module can be extracted
later without schema surgery (ADR-0013).
"""
from modules.elm.models.applications import (
    LeaveApplication,
    LeaveApplicationTransition,
)
from modules.elm.models.balances import LeaveBalance, LeaveTransaction
from modules.elm.models.calendar import Holiday, HolidayCalendar
from modules.elm.models.config import LeavePolicy, SanctionHierarchy
from modules.elm.models.org import EmployeeProfile, OrgUnit, VacationPeriod
from modules.elm.models.records import (
    Notification,
    OfflineLeaveRecord,
    ResumptionRecord,
    SlaEventLog,
)
from modules.elm.models.substitutes import SubstituteAssignment
from modules.elm.models.workflow import LeaveCancellation, LeaveExtension

__all__ = [
    "EmployeeProfile",
    "Holiday",
    "HolidayCalendar",
    "LeaveApplication",
    "LeaveApplicationTransition",
    "LeaveBalance",
    "LeaveCancellation",
    "LeaveExtension",
    "LeavePolicy",
    "LeaveTransaction",
    "Notification",
    "OfflineLeaveRecord",
    "OrgUnit",
    "ResumptionRecord",
    "SanctionHierarchy",
    "SlaEventLog",
    "SubstituteAssignment",
    "VacationPeriod",
]
