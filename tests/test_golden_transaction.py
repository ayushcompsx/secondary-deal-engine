"""
GOLDEN TEST CASE

This is the one fully worked, hand-checked transaction referenced in
FINANCIAL_MODEL.md. Every number below was calculated manually before
any code was written, then encoded here as a regression test. If this
test ever fails after a code change, treat it as a serious signal —
either the hand calculation or the code has a bug, and both must be
re-checked before proceeding.

SCENARIO
--------
Company: TechCo
Last round: $1,000,000,000 post-money, 100,000,000 fully diluted shares
  => last round price = $10.00/share

Seller: Investor A
  - Owns 5,000,000 shares (5% of 100,000,000 total)
  - Acquired 2022-01-01 at cost basis $4.00/share ($20,000,000 total)

Secondary transaction (2024-01-01):
  - Investor A sells 2,000,000 of their 5,000,000 shares
  - Sale price: $9.00/share (10% discount to $10.00 last round price)

Expected seller-side numbers:
  - Gross proceeds = 2,000,000 * $9.00 = $18,000,000
  - Cost basis of shares sold = 2,000,000 * $4.00 = $8,000,000
  - Realized profit = $18,000,000 - $8,000,000 = $10,000,000
  - Realized multiple = $18,000,000 / $8,000,000 = 2.25x
  - Realized XIRR: (1+r)^2 = 2.25 => r = 0.5 (50%), over exactly 2 years

Expected ownership numbers:
  - Seller before: 5,000,000 / 100,000,000 = 5.00%
  - Seller after: 3,000,000 / 100,000,000 = 3.00%
  - SPV after: 2,000,000 / 100,000,000 = 2.00%
  - total_shares_outstanding unchanged at 100,000,000 (share conservation)

Expected buyer-side valuation numbers:
  - Last round price = $10.00/share
  - Secondary price = $9.00/share
  - Premium/discount = ($9.00 - $10.00) / $10.00 = -10% (a 10% discount)

SPV terms:
  - Management fee: 2% of gross investment, paid upfront
  - Carry: 20%, deal-by-deal, American, no hurdle
  - Exit assumption: 2027-01-01 (3 years after SPV investment) at $15.00/share

Expected SPV numbers:
  - Gross investment = $18,000,000 (buys the 2,000,000 shares at $9.00)
  - Management fee = 2% * $18,000,000 = $360,000
  - LP total contribution = $18,000,000 + $360,000 = $18,360,000
  - Exit gross proceeds = 2,000,000 * $15.00 = $30,000,000
  - Profit = $30,000,000 - $18,000,000 = $12,000,000
  - Carry = 20% * $12,000,000 = $2,400,000
  - Net LP distribution = $30,000,000 - $2,400,000 = $27,600,000
  - Gross MOIC = $30,000,000 / $18,000,000 = 1.667x
  - Net MOIC = $27,600,000 / $18,360,000 = 1.503x
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from datetime import date
from decimal import Decimal

import pytest

from domain.models import (
    CapTable,
    Holder,
    HolderType,
    LastRoundValuation,
    SecondaryTransaction,
    SecurityType,
    SPVTerms,
)
from calculations.ownership import apply_secondary_transaction
from calculations.seller_returns import calculate_seller_returns
from calculations.valuation import calculate_buyer_valuation_comparison
from calculations.spv_waterfall import calculate_spv_waterfall


@pytest.fixture
def golden_cap_table() -> CapTable:
    investor_a = Holder(
        holder_id="investor-a",
        holder_name="Investor A",
        holder_type=HolderType.INVESTOR,
        security_type=SecurityType.PREFERRED,
        shares=5_000_000,
        cost_basis_per_share=Decimal("4.00"),
        acquisition_date=date(2022, 1, 1),
    )
    others = Holder(
        holder_id="everyone-else",
        holder_name="Founders, employees, other investors",
        holder_type=HolderType.FOUNDER,
        security_type=SecurityType.COMMON,
        shares=95_000_000,
        cost_basis_per_share=None,
        acquisition_date=None,
    )
    return CapTable(
        company_name="TechCo",
        as_of_date=date(2024, 1, 1),
        total_shares_outstanding=100_000_000,
        holders=(investor_a, others),
    )


@pytest.fixture
def golden_last_round() -> LastRoundValuation:
    return LastRoundValuation(
        round_name="Series D",
        round_date=date(2023, 6, 1),
        post_money_valuation=Decimal("1000000000"),
        fully_diluted_shares=100_000_000,
    )


@pytest.fixture
def golden_transaction() -> SecondaryTransaction:
    return SecondaryTransaction(
        transaction_date=date(2024, 1, 1),
        seller_holder_id="investor-a",
        shares_sold=2_000_000,
        price_per_share=Decimal("9.00"),
    )


def test_ownership_before_and_after(golden_cap_table, golden_transaction):
    result = apply_secondary_transaction(golden_cap_table, golden_transaction)

    assert result.seller_ownership_before_pct == Decimal("5.00")
    assert result.seller_ownership_after_pct == Decimal("3.00")
    assert result.spv_ownership_after_pct == Decimal("2.00")

    # Share conservation
    assert (
        result.cap_table_after.total_shares_outstanding
        == golden_cap_table.total_shares_outstanding
        == 100_000_000
    )


def test_seller_returns(golden_cap_table, golden_transaction):
    seller_before = golden_cap_table.get_holder("investor-a")
    returns = calculate_seller_returns(seller_before, golden_transaction)

    assert returns.gross_proceeds == Decimal("18000000")
    assert returns.cost_basis_of_shares_sold == Decimal("8000000")
    assert returns.realized_profit == Decimal("10000000")
    assert returns.realized_multiple == Decimal("2.25")

    # XIRR should be very close to 50% (exactly 2 years, doubling-and-a-quarter)
    assert returns.realized_xirr is not None
    assert abs(returns.realized_xirr - 0.50) < 0.01


def test_buyer_valuation_comparison(golden_last_round, golden_transaction):
    comparison = calculate_buyer_valuation_comparison(
        golden_last_round, golden_transaction, fully_diluted_shares_at_transaction=100_000_000
    )

    assert comparison.last_round_price_per_share == Decimal("10.00")
    assert comparison.secondary_price_per_share == Decimal("9.00")
    assert comparison.premium_discount_pct == Decimal("-10.00")
    assert comparison.implied_company_valuation_at_secondary == Decimal("900000000")


def test_spv_waterfall(golden_transaction):
    terms = SPVTerms(
        management_fee_pct=Decimal("0.02"),
        carry_pct=Decimal("0.20"),
    )
    result = calculate_spv_waterfall(
        gross_investment=golden_transaction.gross_proceeds,  # $18,000,000
        investment_date=golden_transaction.transaction_date,  # 2024-01-01
        exit_gross_proceeds=Decimal("2000000") * Decimal("15.00"),  # $30,000,000
        exit_date=date(2027, 1, 1),
        terms=terms,
    )

    assert result.gross_investment == Decimal("18000000")
    assert result.management_fee == Decimal("360000.00")
    assert result.lp_total_contribution == Decimal("18360000.00")
    assert result.exit_gross_proceeds == Decimal("30000000")
    assert result.profit == Decimal("12000000")
    assert result.carry == Decimal("2400000.00")
    assert result.net_lp_distribution == Decimal("27600000.00")

    # MOIC checks (allow tiny rounding tolerance on the division)
    assert abs(result.gross_moic - Decimal("1.6667")) < Decimal("0.001")
    assert abs(result.net_moic - Decimal("1.5033")) < Decimal("0.001")

    # IRR sanity: gross MOIC 1.667x over 3 years => gross IRR ~ 18.6%
    assert result.gross_irr is not None
    assert 0.17 < result.gross_irr < 0.20

    assert result.net_irr is not None
    assert 0.14 < result.net_irr < 0.17


def test_seller_cannot_sell_more_shares_than_owned(golden_cap_table):
    from domain.models import SecondaryTransaction
    from calculations.ownership import OwnershipError

    over_sell = SecondaryTransaction(
        transaction_date=date(2024, 1, 1),
        seller_holder_id="investor-a",
        shares_sold=6_000_000,  # seller only owns 5,000,000
        price_per_share=Decimal("9.00"),
    )
    with pytest.raises(OwnershipError):
        apply_secondary_transaction(golden_cap_table, over_sell)


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
