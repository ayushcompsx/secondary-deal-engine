import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from datetime import date
from decimal import Decimal

import pytest

from domain.models import (
    CapTable, Holder, HolderType, LastRoundValuation,
    SecondaryTransaction, SecurityType, SPVTerms,
)
from calculations.deal_service import analyze_deal


@pytest.fixture
def golden_setup():
    cap_table = CapTable(
        company_name="TechCo",
        as_of_date=date(2024, 1, 1),
        total_shares_outstanding=100_000_000,
        holders=(
            Holder("investor-a", "Investor A", HolderType.INVESTOR, SecurityType.PREFERRED,
                   5_000_000, Decimal("4.00"), date(2022, 1, 1)),
            Holder("everyone-else", "Everyone else", HolderType.FOUNDER, SecurityType.COMMON,
                   95_000_000, None, None),
        ),
    )
    last_round = LastRoundValuation("Series D", date(2023, 6, 1), Decimal("1000000000"), 100_000_000)
    transaction = SecondaryTransaction(date(2024, 1, 1), "investor-a", 2_000_000, Decimal("9.00"))
    spv_terms = SPVTerms(Decimal("0.02"), Decimal("0.20"))
    return cap_table, last_round, transaction, spv_terms


def test_full_deal_analysis_matches_golden_numbers(golden_setup):
    cap_table, last_round, transaction, spv_terms = golden_setup

    result = analyze_deal(
        cap_table=cap_table,
        last_round=last_round,
        transaction=transaction,
        spv_terms=spv_terms,
        exit_date=date(2027, 1, 1),
        exit_price_per_share=Decimal("15.00"),
    )

    assert result.validation.is_valid
    assert result.ownership.seller_ownership_after_pct == Decimal("3.00")
    assert result.seller_returns.realized_multiple == Decimal("2.25")
    assert result.buyer_valuation.premium_discount_pct == Decimal("-10.00")
    assert result.spv_waterfall.net_lp_distribution == Decimal("27600000.00")


def test_invalid_transaction_returns_no_calculations(golden_setup):
    cap_table, last_round, _, spv_terms = golden_setup
    bad_transaction = SecondaryTransaction(date(2024, 1, 1), "investor-a", 999_999_999, Decimal("9.00"))

    result = analyze_deal(
        cap_table=cap_table,
        last_round=last_round,
        transaction=bad_transaction,
        spv_terms=spv_terms,
        exit_date=date(2027, 1, 1),
        exit_price_per_share=Decimal("15.00"),
    )

    assert not result.validation.is_valid
    assert result.ownership is None
    assert result.seller_returns is None
    assert result.buyer_valuation is None
    assert result.spv_waterfall is None


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
