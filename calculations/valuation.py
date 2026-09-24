"""
Buyer-side valuation comparison: is the secondary price a premium or
discount to the last primary round?

FORMULA (per spec section 3):
    premium_discount_pct = (secondary_price - last_round_price) / last_round_price

Positive = premium (buyer pays more than last round implied).
Negative = discount (buyer pays less than last round implied).

ASSUMPTION MADE EXPLICIT:
last_round_price is derived as:
    post_money_valuation / fully_diluted_shares
This assumes the last round's post-money valuation and fully diluted
share count are both on a consistent, fully-diluted basis (i.e. the
valuation already reflects the option pool and all share classes).
If the source data does NOT reflect this, the comparison here will be
misleading — this is exactly the kind of ambiguity the spec says must
be surfaced rather than silently assumed away, so it is called out
here and in ASSUMPTIONS.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from domain.models import LastRoundValuation, SecondaryTransaction


@dataclass(frozen=True)
class BuyerValuationComparison:
    last_round_price_per_share: Decimal
    secondary_price_per_share: Decimal
    price_difference_per_share: Decimal
    premium_discount_pct: Decimal  # positive = premium, negative = discount
    implied_company_valuation_at_secondary: Decimal


def calculate_buyer_valuation_comparison(
    last_round: LastRoundValuation,
    transaction: SecondaryTransaction,
    fully_diluted_shares_at_transaction: int,
) -> BuyerValuationComparison:
    last_price = last_round.implied_price_per_share
    secondary_price = transaction.price_per_share

    diff = secondary_price - last_price
    premium_discount_pct = (diff / last_price) * Decimal(100)

    implied_valuation = secondary_price * Decimal(fully_diluted_shares_at_transaction)

    return BuyerValuationComparison(
        last_round_price_per_share=last_price,
        secondary_price_per_share=secondary_price,
        price_difference_per_share=diff,
        premium_discount_pct=premium_discount_pct,
        implied_company_valuation_at_secondary=implied_valuation,
    )
