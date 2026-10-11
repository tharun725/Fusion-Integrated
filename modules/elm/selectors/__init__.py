"""ELM selectors -- every read goes through here.

Ownership and scope live in this package, once, so no
view re-derives them. A foreign id is simply absent
from the queryset, which is why detail views 404
rather than 403: a 403 would leak existence and turn
any id column into an enumeration oracle.
"""
