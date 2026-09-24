"""
Holds the "currently loaded deal" in a simple module-level variable.

This exists so LangChain tools (see agent/tools.py) don't need the LLM
to pass an entire cap table as a giant JSON string on every tool call
— error-prone and wasteful. Instead, the Streamlit UI (or a script)
loads a deal once via `set_current_deal(...)`, and every tool call
reads from here.

This is intentionally simple — a single global "current deal" is
enough for a single-user demo tool. A multi-user production version
would key this by session ID instead, which is called out here as a
known limitation rather than silently ignored.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from domain.models import CapTable, LastRoundValuation, SecondaryTransaction, SPVTerms


@dataclass(frozen=True)
class CurrentDeal:
    cap_table: CapTable
    last_round: LastRoundValuation
    transaction: SecondaryTransaction
    spv_terms: SPVTerms
    exit_date: date
    exit_price_per_share: Decimal

    def as_analyze_deal_kwargs(self) -> dict:
        return {
            "cap_table": self.cap_table,
            "last_round": self.last_round,
            "transaction": self.transaction,
            "spv_terms": self.spv_terms,
            "exit_date": self.exit_date,
            "exit_price_per_share": self.exit_price_per_share,
        }


_current_deal: CurrentDeal | None = None


def set_current_deal(deal: CurrentDeal) -> None:
    global _current_deal
    _current_deal = deal


def get_current_deal() -> CurrentDeal:
    if _current_deal is None:
        raise RuntimeError(
            "No deal is currently loaded. Call set_current_deal(...) before "
            "using any agent tool."
        )
    return _current_deal


def load_golden_example_deal() -> None:
    """Convenience function: loads the same golden example used in the
    test suite, so the agent has something to answer questions about
    immediately, without requiring UI input first."""
    from domain.models import Holder, HolderType, SecurityType

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

    set_current_deal(CurrentDeal(
        cap_table=cap_table,
        last_round=last_round,
        transaction=transaction,
        spv_terms=spv_terms,
        exit_date=date(2027, 1, 1),
        exit_price_per_share=Decimal("15.00"),
    ))
