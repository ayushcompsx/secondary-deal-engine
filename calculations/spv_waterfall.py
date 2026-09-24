"""
SPV waterfall: models LP economics for the single-deal SPV that buys
the secondary position.

WATERFALL STRUCTURE CHOSEN (v1 — explicitly documented, per spec
section 10):
This is a DEAL-BY-DEAL, AMERICAN-STYLE waterfall with NO PREFERRED
RETURN / HURDLE. This is the simplest standard structure for a
single-asset secondary SPV and is chosen deliberately for v1:

    1. LP commits capital = gross_investment (the secondary purchase
       price)
    2. Management fee is charged UPFRONT on committed capital,
       reducing the amount actually invested is NOT assumed here —
       instead, fee is modelled as an ADDITIONAL LP cost on top of
       the investment (i.e. LP contributes gross_investment for the
       asset PLUS the fee, a common structure for pass-through SPVs).
       This assumption is surfaced explicitly; see ASSUMPTIONS.md.
    3. On exit: gross proceeds are received.
    4. Return of capital: LP first gets back gross_investment.
    5. Profit = gross_proceeds - gross_investment.
    6. Carry = carry_pct * profit (taken by the SPV manager/GP).
    7. Net LP distribution = gross_proceeds - carry.
    8. Net LP proceeds (all-in) = net LP distribution - management_fee
       (fee already paid upfront, netted against final LP economics
       for a like-for-like net IRR/TVPI calculation).

FUTURE EXTENSION POINTS (not built in v1, per spec section 10):
    - European/whole-fund waterfall
    - Preferred return / hurdle rate + GP catch-up
    - Clawback provisions
These are deliberately out of scope for the Friday deadline and are
called out here so the waterfall module can be swapped without
touching seller_returns.py, ownership.py, or valuation.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from calculations.xirr import CashFlow, xirr
from domain.models import SPVTerms


class SPVWaterfallError(Exception):
    pass


@dataclass(frozen=True)
class SPVWaterfallResult:
    gross_investment: Decimal
    management_fee: Decimal
    lp_total_contribution: Decimal          # gross_investment + management_fee
    exit_gross_proceeds: Decimal
    return_of_capital: Decimal
    profit: Decimal
    carry: Decimal
    net_lp_distribution: Decimal            # gross_proceeds - carry
    net_lp_proceeds_all_in: Decimal         # net_lp_distribution (fee already sunk cost)
    gross_moic: Decimal                     # exit_gross_proceeds / gross_investment
    net_moic: Decimal                       # net_lp_distribution / lp_total_contribution
    gross_irr: float | None
    net_irr: float | None


def calculate_spv_waterfall(
    gross_investment: Decimal,
    investment_date: date,
    exit_gross_proceeds: Decimal,
    exit_date: date,
    terms: SPVTerms,
) -> SPVWaterfallResult:
    if gross_investment <= 0:
        raise SPVWaterfallError("gross_investment must be positive")
    if exit_gross_proceeds < 0:
        raise SPVWaterfallError("exit_gross_proceeds cannot be negative")
    if exit_date <= investment_date:
        raise SPVWaterfallError("exit_date must be after investment_date")

    management_fee = gross_investment * terms.management_fee_pct
    lp_total_contribution = gross_investment + management_fee

    return_of_capital = min(gross_investment, exit_gross_proceeds)
    profit = max(Decimal(0), exit_gross_proceeds - gross_investment)
    carry = profit * terms.carry_pct

    net_lp_distribution = exit_gross_proceeds - carry
    net_lp_proceeds_all_in = net_lp_distribution  # fee already paid upfront (sunk)

    gross_moic = exit_gross_proceeds / gross_investment
    net_moic = net_lp_distribution / lp_total_contribution

    gross_flows = [
        CashFlow(investment_date, -gross_investment),
        CashFlow(exit_date, exit_gross_proceeds),
    ]
    net_flows = [
        CashFlow(investment_date, -lp_total_contribution),
        CashFlow(exit_date, net_lp_distribution),
    ]

    try:
        gross_irr = xirr(gross_flows)
    except Exception:
        gross_irr = None
    try:
        net_irr = xirr(net_flows)
    except Exception:
        net_irr = None

    return SPVWaterfallResult(
        gross_investment=gross_investment,
        management_fee=management_fee,
        lp_total_contribution=lp_total_contribution,
        exit_gross_proceeds=exit_gross_proceeds,
        return_of_capital=return_of_capital,
        profit=profit,
        carry=carry,
        net_lp_distribution=net_lp_distribution,
        net_lp_proceeds_all_in=net_lp_proceeds_all_in,
        gross_moic=gross_moic,
        net_moic=net_moic,
        gross_irr=gross_irr,
        net_irr=net_irr,
    )
