"""
Ownership transfer logic for a secondary transaction.

CRITICAL DISTINCTION (per the design spec):
A secondary transaction TRANSFERS existing shares from a seller to a
buyer. It does NOT create new shares. total_shares_outstanding is
unchanged before and after. This module enforces that invariant.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from domain.models import CapTable, Holder, HolderType, SecondaryTransaction, SecurityType


class OwnershipError(Exception):
    """Raised when a transaction is invalid against the cap table."""


@dataclass(frozen=True)
class OwnershipResult:
    cap_table_before: CapTable
    cap_table_after: CapTable
    seller_ownership_before_pct: Decimal
    seller_ownership_after_pct: Decimal
    spv_ownership_after_pct: Decimal


def apply_secondary_transaction(
    cap_table: CapTable,
    transaction: SecondaryTransaction,
    spv_holder_id: str = "spv-buyer",
    spv_holder_name: str = "Deal SPV",
) -> OwnershipResult:
    """
    Apply a secondary transaction to a cap table, producing the
    post-transaction cap table.

    Validation:
    - seller must exist in the cap table
    - seller must own at least as many shares as are being sold
    - total_shares_outstanding must be identical before and after
      (share conservation — this is an ownership TRANSFER, not a
      primary issuance)
    """
    seller = cap_table.get_holder(transaction.seller_holder_id)

    if transaction.shares_sold > seller.shares:
        raise OwnershipError(
            f"Seller {seller.holder_id} owns {seller.shares} shares but "
            f"transaction attempts to sell {transaction.shares_sold}"
        )

    seller_before_pct = cap_table.ownership_pct(transaction.seller_holder_id)

    new_holders = []
    for h in cap_table.holders:
        if h.holder_id == transaction.seller_holder_id:
            remaining = h.shares - transaction.shares_sold
            if remaining > 0:
                new_holders.append(
                    Holder(
                        holder_id=h.holder_id,
                        holder_name=h.holder_name,
                        holder_type=h.holder_type,
                        security_type=h.security_type,
                        shares=remaining,
                        cost_basis_per_share=h.cost_basis_per_share,
                        acquisition_date=h.acquisition_date,
                    )
                )
            # if remaining == 0, seller fully exits and is dropped
        else:
            new_holders.append(h)

    # Add (or top up) the SPV as a new holder
    existing_spv = next((h for h in new_holders if h.holder_id == spv_holder_id), None)
    if existing_spv:
        new_holders = [h for h in new_holders if h.holder_id != spv_holder_id]
        spv_shares = existing_spv.shares + transaction.shares_sold
    else:
        spv_shares = transaction.shares_sold

    new_holders.append(
        Holder(
            holder_id=spv_holder_id,
            holder_name=spv_holder_name,
            holder_type=HolderType.SPV,
            security_type=seller.security_type,
            shares=spv_shares,
            cost_basis_per_share=transaction.price_per_share,
            acquisition_date=transaction.transaction_date,
        )
    )

    cap_table_after = CapTable(
        company_name=cap_table.company_name,
        as_of_date=transaction.transaction_date,
        total_shares_outstanding=cap_table.total_shares_outstanding,
        holders=tuple(new_holders),
    )

    # Share conservation invariant check (belt-and-braces, on top of
    # what CapTable.__post_init__ already enforces on construction)
    if cap_table_after.total_shares_outstanding != cap_table.total_shares_outstanding:
        raise OwnershipError(
            "Share conservation violated: total_shares_outstanding changed "
            "across a secondary transaction (this must never happen — a "
            "secondary transfer does not mint new shares)"
        )

    seller_after_pct = (
        cap_table_after.ownership_pct(transaction.seller_holder_id)
        if any(h.holder_id == transaction.seller_holder_id for h in new_holders)
        else Decimal(0)
    )
    spv_after_pct = cap_table_after.ownership_pct(spv_holder_id)

    return OwnershipResult(
        cap_table_before=cap_table,
        cap_table_after=cap_table_after,
        seller_ownership_before_pct=seller_before_pct,
        seller_ownership_after_pct=seller_after_pct,
        spv_ownership_after_pct=spv_after_pct,
    )
