"""
XIRR tests against hand-verifiable and Excel/Google-Sheets-verified
values. If you want to double check any of these, plug the same
dates/amounts into a spreadsheet's XIRR() function.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from datetime import date
from decimal import Decimal

import pytest

from calculations.xirr import CashFlow, XIRRError, xirr


def test_simple_doubling_over_one_year():
    """
    Invest 1,000,000 on day 0, receive 2,000,000 exactly 365 days
    later. This must be exactly 100% (well, extremely close to it,
    since 365/365 = 1.0 year exactly).
    """
    flows = [
        CashFlow(date(2024, 1, 1), Decimal("-1000000")),
        CashFlow(date(2025, 1, 1), Decimal("2000000")),
    ]
    rate = xirr(flows)
    # 2025-01-01 is 366 days after 2024-01-01 (2024 is a leap year),
    # so the rate will be very slightly under 100%.
    assert 0.95 < rate < 1.00


def test_known_two_year_multiple():
    """
    Invest 8,000,000, receive 18,000,000 exactly 2 years later.
    Multiple = 2.25x over 2 years.
    XIRR should satisfy: (1+r)^2 = 2.25  =>  r = sqrt(2.25) - 1 = 0.5
    """
    flows = [
        CashFlow(date(2022, 1, 1), Decimal("-8000000")),
        CashFlow(date(2024, 1, 1), Decimal("18000000")),
    ]
    rate = xirr(flows)
    assert abs(rate - 0.5) < 0.01  # allow small tolerance for leap-day day counts


def test_zero_return_is_negative_100_pct_only_if_zero_proceeds():
    """A total loss (proceeds = 0) should not be a valid XIRR input
    under a strict reading, but a very small residual proceeds value
    should compute to close to -100%."""
    flows = [
        CashFlow(date(2022, 1, 1), Decimal("-1000000")),
        CashFlow(date(2023, 1, 1), Decimal("1")),
    ]
    rate = xirr(flows)
    assert rate < -0.99


def test_requires_at_least_two_cash_flows():
    with pytest.raises(XIRRError):
        xirr([CashFlow(date(2024, 1, 1), Decimal("-1000000"))])


def test_requires_both_positive_and_negative():
    with pytest.raises(XIRRError):
        xirr([
            CashFlow(date(2024, 1, 1), Decimal("1000000")),
            CashFlow(date(2025, 1, 1), Decimal("2000000")),
        ])


def test_rejects_same_day_flows():
    with pytest.raises(XIRRError):
        xirr([
            CashFlow(date(2024, 1, 1), Decimal("-1000000")),
            CashFlow(date(2024, 1, 1), Decimal("2000000")),
        ])


def test_multiple_cash_flows():
    """Two investments, one exit — a more realistic multi-flow case."""
    flows = [
        CashFlow(date(2020, 1, 1), Decimal("-500000")),
        CashFlow(date(2021, 1, 1), Decimal("-500000")),
        CashFlow(date(2024, 1, 1), Decimal("2000000")),
    ]
    rate = xirr(flows)
    # Sanity: should be a positive, double-digit-percent return
    assert 0.10 < rate < 0.40


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
