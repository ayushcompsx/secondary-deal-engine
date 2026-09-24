import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from datetime import date
from decimal import Decimal

import pytest

from domain.models import CapTable, Holder, HolderType, SecondaryTransaction, SecurityType
from validation.checks import validate_full_transaction, ValidationError


@pytest.fixture
def cap_table():
    return CapTable(
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


def test_valid_transaction_passes(cap_table):
    txn = SecondaryTransaction(date(2024, 1, 1), "investor-a", 2_000_000, Decimal("9.00"))
    result = validate_full_transaction(cap_table, txn)
    assert result.is_valid
    result.raise_if_invalid()  # should not raise


def test_unknown_seller_fails(cap_table):
    txn = SecondaryTransaction(date(2024, 1, 1), "nonexistent-holder", 1000, Decimal("9.00"))
    result = validate_full_transaction(cap_table, txn)
    assert not result.is_valid
    assert any("not found" in e for e in result.errors)


def test_overselling_fails(cap_table):
    txn = SecondaryTransaction(date(2024, 1, 1), "investor-a", 6_000_000, Decimal("9.00"))
    result = validate_full_transaction(cap_table, txn)
    assert not result.is_valid
    assert any("owns" in e for e in result.errors)


def test_transaction_before_acquisition_fails(cap_table):
    txn = SecondaryTransaction(date(2021, 1, 1), "investor-a", 1000, Decimal("9.00"))
    result = validate_full_transaction(cap_table, txn)
    assert not result.is_valid
    assert any("before seller's acquisition date" in e for e in result.errors)


def test_raise_if_invalid_actually_raises(cap_table):
    txn = SecondaryTransaction(date(2024, 1, 1), "investor-a", 6_000_000, Decimal("9.00"))
    result = validate_full_transaction(cap_table, txn)
    with pytest.raises(ValidationError):
        result.raise_if_invalid()


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
