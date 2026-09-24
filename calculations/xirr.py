"""
XIRR: date-aware internal rate of return.

WHY NOT PLAIN IRR:
Plain IRR assumes equally-spaced periodic cash flows (e.g. exactly
one per year). Real secondary transactions have irregular dates
(investment on one date, sale on another, arbitrary gap), so we use
XIRR, which solves for the rate r such that:

    sum( cash_flow_i / (1 + r) ** (days_i / 365) ) == 0

where days_i is the number of days between cash_flow_i's date and
the first cash flow's date.

This is implemented from scratch with Newton's method plus a bisection
fallback, so the project has zero paid/external financial-API
dependencies — just Python's standard library.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal


class XIRRError(Exception):
    """Raised when an XIRR cannot be meaningfully calculated."""


@dataclass(frozen=True)
class CashFlow:
    flow_date: date
    amount: Decimal  # negative = outflow (investment), positive = inflow (proceeds)


def _npv(rate: float, flows: list[CashFlow], t0: date) -> float:
    total = 0.0
    for cf in flows:
        days = (cf.flow_date - t0).days
        years = days / 365.0
        total += float(cf.amount) / ((1.0 + rate) ** years)
    return total


def _npv_derivative(rate: float, flows: list[CashFlow], t0: date) -> float:
    total = 0.0
    for cf in flows:
        days = (cf.flow_date - t0).days
        years = days / 365.0
        if years == 0:
            continue
        total += -years * float(cf.amount) / ((1.0 + rate) ** (years + 1))
    return total


def xirr(cash_flows: list[CashFlow], guess: float = 0.15) -> float:
    """
    Solve for XIRR using Newton's method, falling back to bisection
    if Newton's method fails to converge or leaves the sane domain.

    Validation performed up front:
    - Requires at least one negative and one positive cash flow
      (otherwise there is no meaningful rate of return: e.g. all
      outflows, or all inflows, is not a valid investment).
    - Requires at least two distinct dates (a same-day investment
      and exit has an undefined/infinite annualised rate).
    """
    if len(cash_flows) < 2:
        raise XIRRError("XIRR requires at least two cash flows")

    has_negative = any(cf.amount < 0 for cf in cash_flows)
    has_positive = any(cf.amount > 0 for cf in cash_flows)
    if not (has_negative and has_positive):
        raise XIRRError(
            "XIRR requires at least one negative (investment) and one "
            "positive (proceeds) cash flow"
        )

    sorted_flows = sorted(cash_flows, key=lambda cf: cf.flow_date)
    t0 = sorted_flows[0].flow_date

    if all(cf.flow_date == t0 for cf in sorted_flows):
        raise XIRRError(
            "All cash flows occur on the same date; annualised rate is undefined"
        )

    # --- Newton's method ---
    rate = guess
    for _ in range(100):
        npv = _npv(rate, sorted_flows, t0)
        deriv = _npv_derivative(rate, sorted_flows, t0)
        if deriv == 0:
            break
        new_rate = rate - npv / deriv
        if abs(new_rate - rate) < 1e-9:
            return new_rate
        rate = new_rate
        if rate <= -0.999:
            break  # left the sane domain, fall through to bisection

    # --- Bisection fallback (robust but slower) ---
    # Search a wide, progressively-extreme range of low bounds close to
    # -100%. Near-total-loss scenarios (proceeds close to zero) require
    # a bound extremely close to -1 before the tiny residual cash flow's
    # discounted value grows large enough to cross zero.
    high = 10.0  # +1000% annualised, generous upper bound
    npv_high = _npv(high, sorted_flows, t0)
    low = None
    npv_low = None
    for candidate_low in (-0.9999, -0.999999, -0.99999999, -0.9999999999):
        candidate_npv = _npv(candidate_low, sorted_flows, t0)
        if candidate_npv * npv_high < 0:
            low, npv_low = candidate_low, candidate_npv
            break
    if low is None:
        raise XIRRError(
            "Could not bracket a root for XIRR; check cash flow signs/magnitudes"
        )
    for _ in range(200):
        mid = (low + high) / 2
        npv_mid = _npv(mid, sorted_flows, t0)
        if abs(npv_mid) < 1e-6:
            return mid
        if npv_low * npv_mid < 0:
            high = mid
            npv_high = npv_mid
        else:
            low = mid
            npv_low = npv_mid
    return (low + high) / 2
