"""Leave balances and the transaction ledger."""
from django.db import models

from core.db.mixins import TimeStampedModel, UserScopedModel


class LeaveBalance(TimeStampedModel, UserScopedModel):
    """An employee's balance for one category and year.

    ``entitled`` is the annual entitlement; ``opening``
    is what carried in; ``used`` is what was deducted;
    ``lapsed`` is what was lost at year end. Current
    available is ``opening + entitled - used - lapsed``.
    """

    category = models.CharField(max_length=8)
    leave_year = models.CharField(max_length=9)

    entitled = models.FloatField(default=0.0)
    opening = models.FloatField(default=0.0)
    used = models.FloatField(default=0.0)
    lapsed = models.FloatField(default=0.0)

    class Meta:
        db_table = "elm_leave_balance"
        constraints = [
            models.UniqueConstraint(
                fields=["user_id", "category", "leave_year"],
                name="elm_balance_unique_per_year"),
        ]
        indexes = [
            models.Index(fields=["user_id", "leave_year"],
                          name="elm_balance_user_idx")]

    def __str__(self) -> str:
        return (f"balance u{self.user_id} "
                f"{self.category} {self.leave_year}")

    @property
    def available(self) -> float:
        return round(
            self.opening + self.entitled
            - self.used - self.lapsed, 2)


class LeaveTransaction(TimeStampedModel):
    """Append-only ledger of every balance movement."""

    KINDS = [
        ("credit", "Credit"),
        ("debit", "Debit"),
        ("restore", "Restore"),
        ("adjust", "Adjustment"),
        ("carry_forward", "Carry forward"),
        ("conversion", "VL to EL conversion"),
        ("lapse", "Year-end lapse"),
        ("offline", "Offline-sanctioned entry"),
    ]

    balance = models.ForeignKey(
        "LeaveBalance", on_delete=models.PROTECT,
        related_name="transactions")
    user_id = models.IntegerField(db_index=True)
    category = models.CharField(max_length=8)
    leave_year = models.CharField(max_length=9)
    kind = models.CharField(max_length=16, choices=KINDS)
    amount = models.FloatField()
    reference_id = models.IntegerField(
        null=True, blank=True,
        help_text="The application or record that caused this")
    reference_kind = models.CharField(max_length=24,
                                         blank=True)
    note = models.CharField(max_length=300, blank=True)

    class Meta:
        db_table = "elm_leave_transaction"
        indexes = [
            models.Index(fields=["user_id", "leave_year",
                                    "created_at"],
                          name="elm_transaction_user_idx")]
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return (f"txn#{self.pk} {self.kind} "
                f"{self.amount} {self.category}")
