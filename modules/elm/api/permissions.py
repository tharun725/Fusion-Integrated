"""Permission classes for this module.

The two gates -- module grant and permission
code -- are checked on every request. A view
that declares nothing gets only
``IsAuthenticatedPrincipal``, so forgetting
to think about authorization fails closed.
"""
from rest_framework.permissions import BasePermission


class _ModuleScoped(BasePermission):
    """A permission that also requires the
    caller to be an ELM employee (a member
    of some unit), not merely a granted
    user."""
    codes: tuple[str, ...] = ()
    message = "You do not have permission."

    def has_permission(self, request, view):
        principal = getattr(request, "principal", None)
        if principal is None:
            return False
        return principal.has_any_permission(*self.codes)


def ModuleScoped(*codes: str):            # noqa: N802
    return type(
        "ModuleScoped_" + "_".join(codes).replace(".", "_"),
        (_ModuleScoped,), {"codes": codes})
