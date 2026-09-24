"""
Deal service: orchestrates a complete transaction analysis by calling
the deterministic calculation modules in the right order.

This is the ONE function both the Streamlit UI and the AI agent call.
Neither of them re-implements any financial logic — they only call
this (or the narrower functions it wraps) and display/explain the
result. This keeps the deterministic engine as the single source of
truth, per the project's core design rule.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from calculations.ownership import apply_secondary_transaction, OwnershipResult
from calculations.seller_returns import calculate_seller_returns, SellerReturns
from calculations.valuation import calculate_buyer_valuation_comparison, BuyerValuationComparison
from calculations.spv_waterfall import calculate_spv_waterfall, SPVWaterfallResult
from domain.models import CapTable, LastRoundValuation, SecondaryTransaction, SPVTerms
from validation.checks import validate_full_transaction, ValidationResult


@dataclass(frozen=True)
class DealAnalysis:
    """Everything about one secondary + SPV deal, in one place."""
    validation: ValidationResult
    ownership: OwnershipResult | None
    seller_returns: SellerReturns | None
    buyer_valuation: BuyerValuationComparison | None
    spv_waterfall: SPVWaterfallResult | None


def analyze_deal(
    cap_table: CapTable,
    last_round: LastRoundValuation,
    transaction: SecondaryTransaction,
    spv_terms: SPVTerms,
    exit_date: date,
    exit_price_per_share: Decimal,
) -> DealAnalysis:
    """
    Run a complete deal analysis: validate, then calculate ownership
    transfer, seller returns, buyer valuation comparison, and SPV
    waterfall economics, in that order.

    If validation fails, returns a DealAnalysis with is_valid=False
    and every calculation field left as None — this function NEVER
    returns a partially-computed, misleading result. Either the whole
    analysis is valid and complete, or nothing downstream is computed.
    """
    validation = validate_full_transaction(cap_table, transaction)
    if not validation.is_valid:
        return DealAnalysis(
            validation=validation,
            ownership=None,
            seller_returns=None,
            buyer_valuation=None,
            spv_waterfall=None,
        )

    ownership = apply_secondary_transaction(cap_table, transaction)

    seller_before = cap_table.get_holder(transaction.seller_holder_id)
    seller_returns = calculate_seller_returns(seller_before, transaction)

    buyer_valuation = calculate_buyer_valuation_comparison(
        last_round, transaction, cap_table.total_shares_outstanding
    )

    exit_gross_proceeds = Decimal(transaction.shares_sold) * exit_price_per_share
    spv_waterfall = calculate_spv_waterfall(
        gross_investment=transaction.gross_proceeds,
        investment_date=transaction.transaction_date,
        exit_gross_proceeds=exit_gross_proceeds,
        exit_date=exit_date,
        terms=spv_terms,
    )

    return DealAnalysis(
        validation=validation,
        ownership=ownership,
        seller_returns=seller_returns,
        buyer_valuation=buyer_valuation,
        spv_waterfall=spv_waterfall,
    )
