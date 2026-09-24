"""
Domain models for the Secondary & SPV Deal Engine.

Design principles:
- All monetary values use Decimal, never float, to avoid rounding
  errors compounding across a financial calculation chain.
- All models are immutable dataclasses (frozen=True) where possible,
  so a calculation can never accidentally mutate its inputs.
- Dates are explicit (datetime.date), because IRR is time-aware
  (XIRR), not a simple ratio.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import Enum


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class HolderType(str, Enum):
    FOUNDER = "founder"
    EMPLOYEE = "employee"
    INVESTOR = "investor"
    SPV = "spv"
    OPTION_POOL = "option_pool"


class SecurityType(str, Enum):
    COMMON = "common"
    PREFERRED = "preferred"


# ---------------------------------------------------------------------------
# Cap table
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Holder:
    """One line in the cap table."""
    holder_id: str
    holder_name: str
    holder_type: HolderType
    security_type: SecurityType
    shares: int
    cost_basis_per_share: Decimal | None = None  # None if unknown (e.g. founder)
    acquisition_date: date | None = None

    def __post_init__(self) -> None:
        if self.shares < 0:
            raise ValueError(f"Holder {self.holder_id}: shares cannot be negative")
        if self.cost_basis_per_share is not None and self.cost_basis_per_share < 0:
            raise ValueError(f"Holder {self.holder_id}: cost basis cannot be negative")


@dataclass(frozen=True)
class CapTable:
    """
    A snapshot of company ownership at a point in time.

    Invariant enforced at construction: sum of all holder shares equals
    total_shares_outstanding. This is checked eagerly so a malformed
    cap table can never enter the calculation pipeline.
    """
    company_name: str
    as_of_date: date
    total_shares_outstanding: int
    holders: tuple[Holder, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        summed = sum(h.shares for h in self.holders)
        if summed != self.total_shares_outstanding:
            raise ValueError(
                f"Cap table invariant violated: holder shares sum to {summed}, "
                f"but total_shares_outstanding is {self.total_shares_outstanding}"
            )

    def get_holder(self, holder_id: str) -> Holder:
        for h in self.holders:
            if h.holder_id == holder_id:
                return h
        raise KeyError(f"No holder with id {holder_id} in cap table")

    def ownership_pct(self, holder_id: str) -> Decimal:
        holder = self.get_holder(holder_id)
        return (Decimal(holder.shares) / Decimal(self.total_shares_outstanding)) * Decimal(100)


# ---------------------------------------------------------------------------
# Valuation
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LastRoundValuation:
    """
    The most recent primary financing round, used as the reference
    point for premium/discount calculations on a secondary sale.
    """
    round_name: str
    round_date: date
    post_money_valuation: Decimal
    fully_diluted_shares: int

    def __post_init__(self) -> None:
        if self.post_money_valuation <= 0:
            raise ValueError("post_money_valuation must be positive")
        if self.fully_diluted_shares <= 0:
            raise ValueError("fully_diluted_shares must be positive")

    @property
    def implied_price_per_share(self) -> Decimal:
        return self.post_money_valuation / Decimal(self.fully_diluted_shares)


# ---------------------------------------------------------------------------
# Secondary transaction
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SecondaryTransaction:
    """
    A single secondary sale: an existing holder sells existing shares
    to a new buyer (here, an SPV). This is an OWNERSHIP TRANSFER, not
    a primary issuance — total_shares_outstanding does not change.
    """
    transaction_date: date
    seller_holder_id: str
    shares_sold: int
    price_per_share: Decimal

    def __post_init__(self) -> None:
        if self.shares_sold <= 0:
            raise ValueError("shares_sold must be positive")
        if self.price_per_share <= 0:
            raise ValueError("price_per_share must be positive")

    @property
    def gross_proceeds(self) -> Decimal:
        return Decimal(self.shares_sold) * self.price_per_share


# ---------------------------------------------------------------------------
# SPV terms
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SPVTerms:
    """
    Economics of the SPV that acquires the secondary position.

    ASSUMPTION (explicit, documented):
    - Management fee is charged upfront on committed capital
      (i.e. on gross investment amount), a common structure for
      single-deal SPVs.
    - Carry is deal-by-deal, American-style, with NO hurdle rate,
      applied to profit only (proceeds minus gross investment).
      This is the simplest standard structure and is called out
      explicitly so it can be swapped for a European/hurdle waterfall
      later without touching the rest of the engine.
    """
    management_fee_pct: Decimal   # e.g. Decimal("0.02") for 2%
    carry_pct: Decimal            # e.g. Decimal("0.20") for 20%

    def __post_init__(self) -> None:
        if not (Decimal(0) <= self.management_fee_pct <= Decimal("0.10")):
            raise ValueError("management_fee_pct outside sane bounds (0-10%)")
        if not (Decimal(0) <= self.carry_pct <= Decimal("0.50")):
            raise ValueError("carry_pct outside sane bounds (0-50%)")


@dataclass(frozen=True)
class ExitAssumption:
    """A hypothetical future exit used to project SPV/seller returns."""
    exit_date: date
    exit_price_per_share: Decimal

    def __post_init__(self) -> None:
        if self.exit_price_per_share <= 0:
            raise ValueError("exit_price_per_share must be positive")
