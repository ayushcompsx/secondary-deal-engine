"""
Seller-side return calculations for the shares sold in a secondary
transaction.

TVPI DEFINITION USED HERE (documented explicitly, per spec section 8):
This module calculates the REALIZED TVPI on the shares SOLD only:

    realized_TVPI = gross_proceeds / cost_basis_of_shares_sold

It deliberately does NOT include unrealized value of any shares the
seller retains after the transaction — that is a separate, optional
calculation (see `retained_position_value` below) and must not be
silently blended into the realized figure, per the spec's warning
against conflating realized and unrealized value.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from calculations.xirr import CashFlow, xirr
from domain.models import Holder, SecondaryTransaction


class SellerReturnsError(Exception):
    pass


@dataclass(frozen=True)
class SellerReturns:
    shares_sold: int
    gross_proceeds: Decimal
    cost_basis_of_shares_sold: Decimal
    realized_profit: Decimal
    realized_multiple: Decimal      # gross_proceeds / cost_basis (a.k.a. realized TVPI)
    realized_xirr: float | None     # None if cost basis / acquisition date unknown


def calculate_seller_returns(
    seller_before: Holder,
    transaction: SecondaryTransaction,
) -> SellerReturns:
    """
    Calculate the seller's return on the shares sold in this
    transaction.

    Requires the seller's pre-transaction holding to carry a
    cost_basis_per_share and acquisition_date. If either is missing,
    realized_xirr is returned as None with the multiple still
    calculated where cost basis is known — this follows the spec's
    rule to surface missing inputs explicitly rather than inventing
    a number.
    """
    if seller_before.holder_id != transaction.seller_holder_id:
        raise SellerReturnsError("seller_before does not match transaction seller")

    if seller_before.cost_basis_per_share is None:
        raise SellerReturnsError(
            f"Cannot calculate realized returns: holder "
            f"{seller_before.holder_id} has no recorded cost_basis_per_share"
        )

    cost_basis_sold = Decimal(transaction.shares_sold) * seller_before.cost_basis_per_share
    gross_proceeds = transaction.gross_proceeds
    profit = gross_proceeds - cost_basis_sold
    multiple = gross_proceeds / cost_basis_sold

    realized_xirr: float | None = None
    if seller_before.acquisition_date is not None:
        flows = [
            CashFlow(seller_before.acquisition_date, -cost_basis_sold),
            CashFlow(transaction.transaction_date, gross_proceeds),
        ]
        try:
            realized_xirr = xirr(flows)
        except Exception:
            # Same-day or otherwise degenerate case — leave as None
            # rather than raising, since the multiple is still valid
            # and useful even when an annualised rate is undefined.
            realized_xirr = None

    return SellerReturns(
        shares_sold=transaction.shares_sold,
        gross_proceeds=gross_proceeds,
        cost_basis_of_shares_sold=cost_basis_sold,
        realized_profit=profit,
        realized_multiple=multiple,
        realized_xirr=realized_xirr,
    )
