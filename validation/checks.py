"""
Validation layer.

Most invariants (cap table shares summing correctly, no negative
shares, no negative prices, sane fee/carry bounds) are already
enforced at construction time inside domain/models.py — a bad object
simply cannot be created. This module adds the checks that depend on
RELATIONSHIPS between multiple objects (e.g. a cap table + a specific
transaction together), which can't live inside a single model's
__post_init__.

Per the spec: validation errors are explicit, structured, and never
silently corrected. Nothing here "fixes" bad data — it only rejects it
with a clear reason.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from domain.models import CapTable, SecondaryTransaction, SPVTerms


class ValidationError(Exception):
    """Raised when a cross-object validation check fails."""


@dataclass(frozen=True)
class ValidationResult:
    is_valid: bool
    errors: tuple[str, ...] = ()

    def raise_if_invalid(self) -> None:
        if not self.is_valid:
            raise ValidationError("; ".join(self.errors))


def validate_no_duplicate_holder_ids(cap_table: CapTable) -> ValidationResult:
    ids = [h.holder_id for h in cap_table.holders]
    duplicates = {i for i in ids if ids.count(i) > 1}
    if duplicates:
        return ValidationResult(
            is_valid=False,
            errors=(f"Duplicate holder_id(s) found in cap table: {sorted(duplicates)}",),
        )
    return ValidationResult(is_valid=True)


def validate_ownership_sums_to_100(cap_table: CapTable, tolerance: Decimal = Decimal("0.01")) -> ValidationResult:
    """
    Ownership percentages across all holders should sum to ~100%,
    within a small tolerance for rounding. This is a redundant check
    on top of the share-count invariant already enforced in
    CapTable.__post_init__, added here as an explicit, named
    financial sanity check per the spec's validation requirements.
    """
    total_pct = sum(cap_table.ownership_pct(h.holder_id) for h in cap_table.holders)
    diff = abs(total_pct - Decimal(100))
    if diff > tolerance:
        return ValidationResult(
            is_valid=False,
            errors=(f"Ownership percentages sum to {total_pct}%, expected ~100% (diff {diff}%)",),
        )
    return ValidationResult(is_valid=True)


def validate_seller_in_cap_table(cap_table: CapTable, transaction: SecondaryTransaction) -> ValidationResult:
    try:
        cap_table.get_holder(transaction.seller_holder_id)
    except KeyError:
        return ValidationResult(
            is_valid=False,
            errors=(f"Seller '{transaction.seller_holder_id}' not found in cap table",),
        )
    return ValidationResult(is_valid=True)


def validate_seller_has_enough_shares(cap_table: CapTable, transaction: SecondaryTransaction) -> ValidationResult:
    seller = cap_table.get_holder(transaction.seller_holder_id)
    if transaction.shares_sold > seller.shares:
        return ValidationResult(
            is_valid=False,
            errors=(
                f"Seller owns {seller.shares} shares but transaction sells "
                f"{transaction.shares_sold}",
            ),
        )
    return ValidationResult(is_valid=True)


def validate_transaction_date_after_acquisition(cap_table: CapTable, transaction: SecondaryTransaction) -> ValidationResult:
    seller = cap_table.get_holder(transaction.seller_holder_id)
    if seller.acquisition_date is not None and transaction.transaction_date < seller.acquisition_date:
        return ValidationResult(
            is_valid=False,
            errors=(
                f"Transaction date {transaction.transaction_date} is before "
                f"seller's acquisition date {seller.acquisition_date}",
            ),
        )
    return ValidationResult(is_valid=True)


def validate_full_transaction(cap_table: CapTable, transaction: SecondaryTransaction) -> ValidationResult:
    """Runs every cross-object check and combines the results."""
    checks = [
        validate_no_duplicate_holder_ids(cap_table),
        validate_ownership_sums_to_100(cap_table),
        validate_seller_in_cap_table(cap_table, transaction),
    ]
    # Only run seller-share and date checks if the seller actually exists,
    # otherwise get_holder() inside them would raise a KeyError itself.
    if checks[-1].is_valid:
        checks.append(validate_seller_has_enough_shares(cap_table, transaction))
        checks.append(validate_transaction_date_after_acquisition(cap_table, transaction))

    all_errors = tuple(e for r in checks for e in r.errors)
    return ValidationResult(is_valid=len(all_errors) == 0, errors=all_errors)
