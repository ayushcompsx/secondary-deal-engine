"""
LangChain tool wrappers around the deterministic calculation engine.

CRITICAL RULE (per the project's core design principle):
These tools NEVER calculate anything themselves. Each one simply
formats inputs, calls a function from calculations/, and formats the
output as text for the LLM to read. The LLM decides WHICH tool to
call and in WHAT ORDER, but it never invents a number — every figure
the agent ever states came from one of these deterministic function
calls.

Tools operate on a single "current deal" held in memory (see
current_deal.py) so the LLM doesn't need to pass the entire cap table
as a giant string on every single tool call.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from langchain.tools import tool

from agent.current_deal import get_current_deal
from calculations.deal_service import analyze_deal


@tool
def get_seller_returns() -> str:
    """
    Use this to answer questions about the SELLER's side of the deal:
    how much cash they received, their profit, their return multiple,
    and their annualised (XIRR) return. Takes no arguments — it reads
    the currently loaded deal.
    """
    deal = get_current_deal()
    result = analyze_deal(**deal.as_analyze_deal_kwargs())

    if not result.validation.is_valid:
        return f"Cannot compute seller returns: deal is invalid. Errors: {'; '.join(result.validation.errors)}"

    sr = result.seller_returns
    xirr_str = f"{sr.realized_xirr:.1%}" if sr.realized_xirr is not None else "not available (missing dates)"
    return (
        f"Seller sold {sr.shares_sold:,} shares.\n"
        f"Gross proceeds: {sr.gross_proceeds:,.2f}\n"
        f"Cost basis of shares sold: {sr.cost_basis_of_shares_sold:,.2f}\n"
        f"Realized profit: {sr.realized_profit:,.2f}\n"
        f"Realized multiple: {sr.realized_multiple:.2f}x\n"
        f"Realized XIRR (annualised return): {xirr_str}"
    )


@tool
def get_buyer_valuation_comparison() -> str:
    """
    Use this to answer questions about whether the buyer is paying a
    PREMIUM or DISCOUNT versus the company's last funding round
    valuation. Takes no arguments — it reads the currently loaded deal.
    """
    deal = get_current_deal()
    result = analyze_deal(**deal.as_analyze_deal_kwargs())

    if not result.validation.is_valid:
        return f"Cannot compute buyer valuation: deal is invalid. Errors: {'; '.join(result.validation.errors)}"

    bv = result.buyer_valuation
    direction = "PREMIUM" if bv.premium_discount_pct > 0 else "DISCOUNT"
    return (
        f"Last round price per share: {bv.last_round_price_per_share:,.2f}\n"
        f"Secondary price per share: {bv.secondary_price_per_share:,.2f}\n"
        f"This is a {direction} of {abs(bv.premium_discount_pct):.2f}% versus the last round.\n"
        f"Implied company valuation at this secondary price: {bv.implied_company_valuation_at_secondary:,.2f}"
    )


@tool
def get_spv_waterfall() -> str:
    """
    Use this to answer questions about the SPV / LP side of the deal:
    management fees, carried interest, gross and net returns for the
    investors who put money into the SPV. Takes no arguments — it reads
    the currently loaded deal.
    """
    deal = get_current_deal()
    result = analyze_deal(**deal.as_analyze_deal_kwargs())

    if not result.validation.is_valid:
        return f"Cannot compute SPV waterfall: deal is invalid. Errors: {'; '.join(result.validation.errors)}"

    w = result.spv_waterfall
    gross_irr_str = f"{w.gross_irr:.1%}" if w.gross_irr is not None else "not available"
    net_irr_str = f"{w.net_irr:.1%}" if w.net_irr is not None else "not available"
    return (
        f"Gross investment: {w.gross_investment:,.2f}\n"
        f"Management fee: {w.management_fee:,.2f}\n"
        f"LP total contribution (investment + fee): {w.lp_total_contribution:,.2f}\n"
        f"Exit gross proceeds: {w.exit_gross_proceeds:,.2f}\n"
        f"Profit: {w.profit:,.2f}\n"
        f"Carry taken by manager: {w.carry:,.2f}\n"
        f"Net LP distribution (after carry): {w.net_lp_distribution:,.2f}\n"
        f"Gross MOIC: {w.gross_moic:.2f}x | Net MOIC: {w.net_moic:.2f}x\n"
        f"Gross IRR: {gross_irr_str} | Net IRR: {net_irr_str}"
    )


@tool
def get_ownership_summary() -> str:
    """
    Use this to answer questions about cap table ownership before and
    after the secondary transaction — who owns what percentage of the
    company. Takes no arguments — it reads the currently loaded deal.
    """
    deal = get_current_deal()
    result = analyze_deal(**deal.as_analyze_deal_kwargs())

    if not result.validation.is_valid:
        return f"Cannot compute ownership: deal is invalid. Errors: {'; '.join(result.validation.errors)}"

    o = result.ownership
    return (
        f"Seller ownership before transaction: {o.seller_ownership_before_pct:.2f}%\n"
        f"Seller ownership after transaction: {o.seller_ownership_after_pct:.2f}%\n"
        f"SPV ownership after transaction: {o.spv_ownership_after_pct:.2f}%\n"
        f"Total shares outstanding unchanged at: {o.cap_table_after.total_shares_outstanding:,} "
        f"(confirms this was a share transfer, not new issuance)"
    )


@tool
def validate_current_deal() -> str:
    """
    Use this if asked whether the currently loaded deal is valid, or
    if any other tool reports the deal is invalid and you need the
    full list of validation errors. Takes no arguments.
    """
    deal = get_current_deal()
    result = analyze_deal(**deal.as_analyze_deal_kwargs())

    if result.validation.is_valid:
        return "The deal is valid — all cap table, ownership, and transaction checks passed."
    return "The deal is INVALID. Errors: " + "; ".join(result.validation.errors)


ALL_TOOLS = [
    get_seller_returns,
    get_buyer_valuation_comparison,
    get_spv_waterfall,
    get_ownership_summary,
    validate_current_deal,
]
