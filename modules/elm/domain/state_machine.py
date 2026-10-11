"""The ELM state machines.

Declarative tables of legal moves, so an illegal transition is
impossible to express rather than merely rejected. Pure Python, so
the rules test in milliseconds with no database.

The four machines mirror the workflow specifications:

    LeaveApplication      new leave (CW-EL-01, BW-EL-01..09)
    LeaveCancellation     pre-start cancellation (CW-EL-02, BW-EL-10..11)
    LeaveExtension        ongoing-leave extension (CW-EL-03, BW-EL-12..14)
    ResumptionRecord      return-to-duty review (CW-EL-04, BW-EL-15..17)
"""
from __future__ import annotations

from dataclasses import dataclass, field


class InvalidTransition(Exception):
    def __init__(self, frm: str, to: str, machine: str = ""):
        scope = f"{machine}: " if machine else ""
        super().__init__(f"{scope}cannot move from {frm!r} to {to!r}.")
        self.frm, self.to, self.machine = frm, to, machine


class ActorNotAllowed(Exception):
    def __init__(self, actor_kind: str, frm: str, to: str, machine: str = ""):
        super().__init__(
            f"A {actor_kind} may not move {machine} from {frm!r} to {to!r}.")
        self.actor_kind, self.frm, self.to, self.machine = (
            actor_kind, frm, to, machine)


# -- Actor lanes --------------------------------------------------------
EMPLOYEE = "employee"            # the applicant
SUBSTITUTE = "substitute"        # responsibility holder
UNIT_HEAD = "unit_head"          # head of the applicant's unit
ESTABLISHMENT = "establishment"  # Deputy Registrar (Estt.) processing
AUTHORITY = "authority"          # final sanctioning authority
SYSTEM = "system"                # scheduled: year-end, SLA sweeps


@dataclass(frozen=True)
class Transition:
    frm: str
    to: str
    actors: frozenset[str]
    guards: tuple[str, ...] = field(default_factory=tuple)


def _index(transitions):
    return {(t.frm, t.to): t for t in transitions}


def resolve(transitions, index, frm: str, to: str,
            actor_kind: str | None = None, machine: str = "") -> Transition:
    t = index.get((frm, to))
    if t is None:
        raise InvalidTransition(frm, to, machine)
    if actor_kind is not None and actor_kind not in t.actors:
        raise ActorNotAllowed(actor_kind, frm, to, machine)
    return t


def is_legal(transitions, index, frm: str, to: str) -> bool:
    return (frm, to) in index


def allowed_targets(transitions, frm: str,
                    actor_kind: str | None = None) -> list[str]:
    return sorted(t.to for t in transitions
                  if t.frm == frm
                  and (actor_kind is None or actor_kind in t.actors))


# ======================================================================
# LeaveApplication -- new leave (BW-EL-01..09)
# ======================================================================
# New-leave states.
DRAFT = "draft"
AWAITING_SUBSTITUTE = "awaiting_substitute_response"
APPLICANT_ACTION = "applicant_action_required"
AWAITING_UNIT_HEAD = "awaiting_unit_head_review"
AWAITING_ESTABLISHMENT = "awaiting_establishment_routing"
AWAITING_FINAL = "awaiting_final_sanction_decision"
AWAITING_DIRECTOR = "awaiting_director_self_sanction"
APPROVED = "approved"
REJECTED = "rejected"
WITHDRAWN = "withdrawn"
ONGOING = "ongoing"
CANCELLED = "cancelled"

#: Pending means "not yet finally decided", so withdrawal is open
#: (BR-EL-022) and SLA reminders may fire.
PENDING_STATES = frozenset({
    DRAFT, AWAITING_SUBSTITUTE, APPLICANT_ACTION, AWAITING_UNIT_HEAD,
    AWAITING_ESTABLISHMENT, AWAITING_FINAL, AWAITING_DIRECTOR,
})

TERMINAL = frozenset({APPROVED, REJECTED, WITHDRAWN, CANCELLED})


NEW_LEAVE_TRANSITIONS: tuple[Transition, ...] = (
    # Submission (EL-UC-001). Which gate opens depends on substitute
    # requirement and whether the Director is the applicant.
    Transition(DRAFT, AWAITING_SUBSTITUTE, frozenset({EMPLOYEE}),
               ("valid_submission", "substitute_required")),
    Transition(DRAFT, AWAITING_UNIT_HEAD, frozenset({EMPLOYEE}),
               ("valid_submission", "no_substitute", "not_director")),
    Transition(DRAFT, AWAITING_DIRECTOR, frozenset({EMPLOYEE}),
               ("valid_submission", "no_substitute", "director_applicant")),

    # Substitute consent gate (EL-UC-002, EL-UC-019).
    Transition(AWAITING_SUBSTITUTE, APPLICANT_ACTION,
               frozenset({SUBSTITUTE}), ("substitute_declined",)),
    Transition(APPLICANT_ACTION, AWAITING_SUBSTITUTE,
               frozenset({EMPLOYEE}), ("replacement_nominated",)),
    Transition(AWAITING_SUBSTITUTE, AWAITING_UNIT_HEAD,
               frozenset({SUBSTITUTE}),
               ("substitute_accepted", "not_director")),
    Transition(AWAITING_SUBSTITUTE, AWAITING_DIRECTOR,
               frozenset({SUBSTITUTE}),
               ("substitute_accepted", "director_applicant")),

    # Unit Head review (EL-UC-003). Final for CL/RH; recommends for
    # SCL/EL/COL/VL, after which the request routes onward.
    Transition(AWAITING_UNIT_HEAD, APPROVED, frozenset({UNIT_HEAD}),
               ("cl_rh_final", "approve")),
    Transition(AWAITING_UNIT_HEAD, REJECTED, frozenset({UNIT_HEAD}),
               ("cl_rh_final", "reject")),
    Transition(AWAITING_UNIT_HEAD, AWAITING_ESTABLISHMENT,
               frozenset({UNIT_HEAD}),
               ("higher_sanction", "establishment_configured")),
    Transition(AWAITING_UNIT_HEAD, AWAITING_FINAL, frozenset({UNIT_HEAD}),
               ("higher_sanction", "no_establishment_step")),

    # Establishment verify-and-route (EL-UC-004), where configured.
    Transition(AWAITING_ESTABLISHMENT, AWAITING_FINAL,
               frozenset({ESTABLISHMENT}), ("routing_valid",)),

    # Final sanction (EL-UC-005).
    Transition(AWAITING_FINAL, APPROVED, frozenset({AUTHORITY}),
               ("final_approve",)),
    Transition(AWAITING_FINAL, REJECTED, frozenset({AUTHORITY}),
               ("final_reject",)),

    # Director self-sanction (BR-EL-020): the Director is both
    # applicant and authority, so the normal route is replaced.
    Transition(AWAITING_DIRECTOR, APPROVED, frozenset({AUTHORITY}),
               ("director_self_sanction",)),
    Transition(AWAITING_DIRECTOR, REJECTED, frozenset({AUTHORITY}),
               ("director_self_sanction",)),

    # Withdrawal terminates every pending state immediately
    # (EL-UC-007, BR-EL-022). No transition from a terminal state.
    *(Transition(s, WITHDRAWN, frozenset({EMPLOYEE}))
      for s in PENDING_STATES),

    # A leave that has begun is ongoing (EL/COL/VL extension base).
    Transition(APPROVED, ONGOING, frozenset({SYSTEM}),
               ("leave_commenced",)),
    # Cancellation approval marks the leave cancelled without editing
    # it in place; the cancellation itself lives on its own machine.
    Transition(APPROVED, CANCELLED, frozenset({SYSTEM}),
               ("cancellation_approved",)),
    Transition(ONGOING, CANCELLED, frozenset({SYSTEM}),
               ("cancellation_approved",)),
)

NEW_LEAVE_INDEX = _index(NEW_LEAVE_TRANSITIONS)


# ======================================================================
# LeaveCancellation -- pre-start reversal (BW-EL-10..11)
# ======================================================================
CANCEL_PENDING_UH = "cancellation_pending_unit_head"
CANCEL_PENDING_EST = "cancellation_pending_establishment"
CANCEL_PENDING_FINAL = "cancellation_pending_final"
CANCEL_APPROVED = "cancellation_approved"
CANCEL_REJECTED = "cancellation_rejected"

CANCELLATION_TERMINAL = frozenset({CANCEL_APPROVED, CANCEL_REJECTED})

CANCELLATION_TRANSITIONS: tuple[Transition, ...] = (
    # Created directly in the first state by the request itself.
    Transition(CANCEL_PENDING_UH, CANCEL_PENDING_EST,
               frozenset({UNIT_HEAD}),
               ("higher_sanction", "establishment_configured")),
    Transition(CANCEL_PENDING_UH, CANCEL_PENDING_FINAL,
               frozenset({UNIT_HEAD}),
               ("higher_sanction", "no_establishment_step")),
    # CL/RH: the Unit Head decides cancellation outright.
    Transition(CANCEL_PENDING_UH, CANCEL_APPROVED, frozenset({UNIT_HEAD}),
               ("cl_rh_final", "approve")),
    Transition(CANCEL_PENDING_UH, CANCEL_REJECTED, frozenset({UNIT_HEAD}),
               ("cl_rh_final", "reject")),
    Transition(CANCEL_PENDING_EST, CANCEL_PENDING_FINAL,
               frozenset({ESTABLISHMENT}), ("routing_valid",)),
    Transition(CANCEL_PENDING_FINAL, CANCEL_APPROVED,
               frozenset({AUTHORITY}), ("final_approve",)),
    Transition(CANCEL_PENDING_FINAL, CANCEL_REJECTED,
               frozenset({AUTHORITY}), ("final_reject",)),
)

CANCELLATION_INDEX = _index(CANCELLATION_TRANSITIONS)


# ======================================================================
# LeaveExtension -- additional time while EL/COL/VL is ongoing
# (BW-EL-12..14)
# ======================================================================
EXT_AWAITING_SUBSTITUTE = "extension_awaiting_substitute"
EXT_APPLICANT_ACTION = "extension_applicant_action_required"
EXT_AWAITING_UNIT_HEAD = "extension_awaiting_unit_head"
EXT_PENDING_EST = "extension_pending_establishment"
EXT_PENDING_FINAL = "extension_pending_final"
EXT_APPROVED = "extension_approved"
EXT_REJECTED = "extension_rejected"

EXTENSION_PENDING_STATES = frozenset({
    EXT_AWAITING_SUBSTITUTE, EXT_APPLICANT_ACTION,
    EXT_AWAITING_UNIT_HEAD, EXT_PENDING_EST, EXT_PENDING_FINAL,
})
EXTENSION_TERMINAL = frozenset({EXT_APPROVED, EXT_REJECTED})

EXTENSION_TRANSITIONS: tuple[Transition, ...] = (
    Transition(EXT_AWAITING_SUBSTITUTE, EXT_APPLICANT_ACTION,
               frozenset({SUBSTITUTE}), ("substitute_declined",)),
    Transition(EXT_APPLICANT_ACTION, EXT_AWAITING_SUBSTITUTE,
               frozenset({EMPLOYEE}), ("replacement_nominated",)),
    Transition(EXT_AWAITING_SUBSTITUTE, EXT_AWAITING_UNIT_HEAD,
               frozenset({SUBSTITUTE}), ("substitute_accepted",)),
    Transition(EXT_AWAITING_UNIT_HEAD, EXT_PENDING_EST,
               frozenset({UNIT_HEAD}),
               ("higher_sanction", "establishment_configured")),
    Transition(EXT_AWAITING_UNIT_HEAD, EXT_PENDING_FINAL,
               frozenset({UNIT_HEAD}),
               ("higher_sanction", "no_establishment_step")),
    Transition(EXT_PENDING_EST, EXT_PENDING_FINAL,
               frozenset({ESTABLISHMENT}), ("routing_valid",)),
    Transition(EXT_PENDING_FINAL, EXT_APPROVED, frozenset({AUTHORITY}),
               ("final_approve",)),
    Transition(EXT_PENDING_FINAL, EXT_REJECTED, frozenset({AUTHORITY}),
               ("final_reject",)),
    *(Transition(s, EXT_REJECTED, frozenset({EMPLOYEE}))
      for s in EXTENSION_PENDING_STATES),
)

EXTENSION_INDEX = _index(EXTENSION_TRANSITIONS)


# ======================================================================
# ResumptionRecord -- return to duty after EL/COL/VL (BW-EL-15..17)
# ======================================================================
RESUMPTION_PENDING = "resumption_review_pending"
RESUMPTION_NO_ADJUSTMENT = "resumption_reviewed_no_adjustment"
RESUMPTION_ADJUSTED = "resumption_reviewed_adjusted"

RESUMPTION_TERMINAL = frozenset({RESUMPTION_NO_ADJUSTMENT,
                                 RESUMPTION_ADJUSTED})

RESUMPTION_TRANSITIONS: tuple[Transition, ...] = (
    # Submitted directly in the pending state by the employee.
    Transition(RESUMPTION_PENDING, RESUMPTION_NO_ADJUSTMENT,
               frozenset({AUTHORITY}), ("dates_match",)),
    Transition(RESUMPTION_PENDING, RESUMPTION_ADJUSTED,
               frozenset({AUTHORITY}), ("dates_differ",)),
)

RESUMPTION_INDEX = _index(RESUMPTION_TRANSITIONS)


#: Every machine, keyed by name, so services resolve through one
#: helper instead of four near-identical copies.
MACHINES = {
    "leave": (NEW_LEAVE_TRANSITIONS, NEW_LEAVE_INDEX),
    "cancellation": (CANCELLATION_TRANSITIONS, CANCELLATION_INDEX),
    "extension": (EXTENSION_TRANSITIONS, EXTENSION_INDEX),
    "resumption": (RESUMPTION_TRANSITIONS, RESUMPTION_INDEX),
}


def resolve_transition(machine: str, frm: str, to: str,
                       actor_kind: str | None = None) -> Transition:
    transitions, index = MACHINES[machine]
    return resolve(transitions, index, frm, to, actor_kind, machine)


def is_legal_transition(machine: str, frm: str, to: str) -> bool:
    transitions, index = MACHINES[machine]
    return is_legal(transitions, index, frm, to)


def allowed_targets_for(machine: str, frm: str,
                        actor_kind: str | None = None) -> list[str]:
    transitions, _ = MACHINES[machine]
    return allowed_targets(transitions, frm, actor_kind)


__all__ = [
    "APPLICANT_ACTION",
    "APPROVED",
    "AUTHORITY",
    "AWAITING_DIRECTOR",
    "AWAITING_ESTABLISHMENT",
    "AWAITING_FINAL",
    "AWAITING_SUBSTITUTE",
    "AWAITING_UNIT_HEAD",
    "CANCELLED",
    "CANCEL_APPROVED",
    "CANCEL_PENDING_EST",
    "CANCEL_PENDING_FINAL",
    "CANCEL_PENDING_UH",
    "CANCEL_REJECTED",
    "DRAFT",
    "EMPLOYEE",
    "ESTABLISHMENT",
    "EXT_APPLICANT_ACTION",
    "EXT_APPROVED",
    "EXT_AWAITING_SUBSTITUTE",
    "EXT_AWAITING_UNIT_HEAD",
    "EXT_PENDING_EST",
    "EXT_PENDING_FINAL",
    "EXT_REJECTED",
    "MACHINES",
    "ONGOING",
    "PENDING_STATES",
    "REJECTED",
    "RESUMPTION_ADJUSTED",
    "RESUMPTION_NO_ADJUSTMENT",
    "RESUMPTION_PENDING",
    "SUBSTITUTE",
    "SYSTEM",
    "TERMINAL",
    "UNIT_HEAD",
    "WITHDRAWN",
    "allowed_targets_for",
    "is_legal_transition",
    "resolve_transition",
]
