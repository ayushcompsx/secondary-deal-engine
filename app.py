"""
Streamlit UI for the Secondary & SPV Deal Engine.

Run with:  streamlit run app.py

This UI is a thin presentation layer only. It does NOT recalculate
anything itself — every number shown comes from calling
calculations/deal_service.py's analyze_deal(), the same function used
by the AI agent and the test suite. This keeps the UI, the agent, and
the tests all reading from one single source of truth.
"""

from __future__ import annotations

import sys
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import streamlit as st

from domain.models import (
    CapTable, Holder, HolderType, LastRoundValuation,
    SecondaryTransaction, SecurityType, SPVTerms,
)
from calculations.deal_service import analyze_deal


st.set_page_config(page_title="Secondary & SPV Deal Engine", layout="wide")

# ---------------------------------------------------------------------------
# Custom theme: dark navy background, serif headings, gold accents.
# Streamlit can't do full page-transition animations, but this gets us
# a considered, premium-fintech feel with subtle fade-ins and hover states.
# ---------------------------------------------------------------------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@500;600&family=Inter:wght@400;500;600&display=swap');

:root {
    --navy-bg: #0f1b2d;
    --navy-card: #16273e;
    --navy-border: #2a3d54;
    --gold: #c9a94d;
    --text-primary: #f3f4f0;
    --text-secondary: #8ea3bd;
    --text-muted: #6b7f96;
}

.stApp, div[data-testid="stAppViewContainer"], div[data-testid="stMain"] {
    background-color: var(--navy-bg) !important;
}
[data-testid="stHeader"] {
    background-color: transparent !important;
}

/* Sidebar */
section[data-testid="stSidebar"] {
    background-color: var(--navy-card);
    border-right: 1px solid var(--navy-border);
}
section[data-testid="stSidebar"] * {
    color: var(--text-primary) !important;
    font-family: 'Inter', sans-serif !important;
}

/* Headings — serif, matching the "held in London" editorial feel */
h1, h2, h3 {
    font-family: 'Playfair Display', Georgia, serif !important;
    color: var(--text-primary) !important;
    letter-spacing: 0.2px;
}
h1 { font-size: 32px !important; font-weight: 600 !important; }
h2 { font-size: 22px !important; font-weight: 500 !important; margin-top: 1.5rem !important; }

/* Body / caption text */
p, span, label, div[data-testid="stMarkdownContainer"] p {
    font-family: 'Inter', sans-serif;
    color: var(--text-secondary) !important;
}

/* Metric cards — fade in on load, subtle hover lift */
div[data-testid="stMetric"] {
    background-color: var(--navy-card);
    border: 1px solid var(--navy-border);
    border-radius: 10px;
    padding: 16px 18px;
    animation: fadeIn 0.6s ease-out;
    transition: transform 0.15s ease, border-color 0.15s ease;
}
div[data-testid="stMetric"]:hover {
    transform: translateY(-2px);
    border-color: var(--gold);
}
div[data-testid="stMetricLabel"] {
    color: var(--text-secondary) !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 11px !important;
    letter-spacing: 1px;
    text-transform: uppercase;
}
div[data-testid="stMetricValue"] {
    color: var(--gold) !important;
    font-family: 'Playfair Display', serif !important;
    font-size: 28px !important;
}

@keyframes fadeIn {
    from { opacity: 0; transform: translateY(8px); }
    to { opacity: 1; transform: translateY(0); }
}

/* Success / error banners */
div[data-testid="stAlert"] {
    background-color: var(--navy-card) !important;
    border: 1px solid var(--gold) !important;
    border-radius: 8px !important;
    animation: fadeIn 0.5s ease-out;
}
div[data-testid="stAlert"] p {
    color: var(--text-primary) !important;
}

/* Buttons */
.stButton button {
    background-color: transparent !important;
    color: var(--gold) !important;
    border: 1px solid var(--gold) !important;
    border-radius: 6px !important;
    font-family: 'Inter', sans-serif !important;
    letter-spacing: 0.5px;
    transition: background-color 0.15s ease, color 0.15s ease;
}
.stButton button:hover {
    background-color: var(--gold) !important;
    color: var(--navy-bg) !important;
}

/* Text input */
.stTextInput input {
    background-color: var(--navy-card) !important;
    color: var(--text-primary) !important;
    border: 1px solid var(--navy-border) !important;
    border-radius: 6px !important;
    font-family: 'Inter', sans-serif !important;
}

/* Divider */
hr {
    border-color: var(--navy-border) !important;
}

/* Sidebar number inputs / sliders */
input, .stSlider {
    color: var(--text-primary) !important;
}
</style>
""", unsafe_allow_html=True)

st.title("Secondary & SPV Deal Engine")
st.caption(
    "A deterministic financial engine for modelling late-stage secondary "
    "transactions wrapped in an SPV. Every figure below is calculated by "
    "tested, hand-verified formulas — nothing here is estimated by AI."
)

# ---------------------------------------------------------------------------
# Sidebar: inputs
# ---------------------------------------------------------------------------

st.sidebar.header("Company & Last Round")
company_name = st.sidebar.text_input("Company name", value="TechCo")
last_round_valuation = st.sidebar.number_input(
    "Last round post-money valuation ($)", min_value=0.0, value=1_000_000_000.0, step=1_000_000.0
)
fully_diluted_shares = st.sidebar.number_input(
    "Fully diluted shares outstanding", min_value=1, value=100_000_000, step=1_000_000
)

st.sidebar.header("Seller")
seller_name = st.sidebar.text_input("Seller name", value="Investor A")
seller_shares_owned = st.sidebar.number_input(
    "Seller shares owned (before sale)", min_value=1, value=5_000_000, step=100_000
)
seller_cost_basis = st.sidebar.number_input(
    "Seller cost basis per share ($)", min_value=0.0, value=4.00, step=0.10, format="%.2f"
)
seller_acquisition_date = st.sidebar.date_input("Seller acquisition date", value=date(2022, 1, 1))

st.sidebar.header("Secondary Transaction")
transaction_date_input = st.sidebar.date_input("Transaction date", value=date(2024, 1, 1))
shares_sold = st.sidebar.number_input(
    "Shares sold", min_value=1, value=2_000_000, step=100_000
)
secondary_price = st.sidebar.number_input(
    "Secondary price per share ($)", min_value=0.01, value=9.00, step=0.10, format="%.2f"
)

st.sidebar.header("SPV Terms")
management_fee_pct = st.sidebar.slider("Management fee (%)", 0.0, 5.0, 2.0, 0.1) / 100
carry_pct = st.sidebar.slider("Carry (%)", 0.0, 30.0, 20.0, 1.0) / 100

st.sidebar.header("Exit Assumption")
exit_date_input = st.sidebar.date_input("Exit date", value=date(2027, 1, 1))
exit_price = st.sidebar.number_input(
    "Exit price per share ($)", min_value=0.01, value=15.00, step=0.50, format="%.2f"
)

st.sidebar.caption(
    "Waterfall model: deal-by-deal, American-style, no hurdle. "
    "Management fee charged upfront on gross investment. "
    "See ASSUMPTIONS.md for full detail."
)


# ---------------------------------------------------------------------------
# Build domain objects from inputs
# ---------------------------------------------------------------------------

def build_deal():
    other_shares = fully_diluted_shares - seller_shares_owned
    cap_table = CapTable(
        company_name=company_name,
        as_of_date=transaction_date_input,
        total_shares_outstanding=fully_diluted_shares,
        holders=(
            Holder(
                holder_id="seller",
                holder_name=seller_name,
                holder_type=HolderType.INVESTOR,
                security_type=SecurityType.PREFERRED,
                shares=seller_shares_owned,
                cost_basis_per_share=Decimal(str(seller_cost_basis)),
                acquisition_date=seller_acquisition_date,
            ),
            Holder(
                holder_id="everyone-else",
                holder_name="Everyone else",
                holder_type=HolderType.FOUNDER,
                security_type=SecurityType.COMMON,
                shares=other_shares,
                cost_basis_per_share=None,
                acquisition_date=None,
            ),
        ),
    )

    last_round = LastRoundValuation(
        round_name="Last round",
        round_date=transaction_date_input,
        post_money_valuation=Decimal(str(last_round_valuation)),
        fully_diluted_shares=fully_diluted_shares,
    )

    transaction = SecondaryTransaction(
        transaction_date=transaction_date_input,
        seller_holder_id="seller",
        shares_sold=shares_sold,
        price_per_share=Decimal(str(secondary_price)),
    )

    spv_terms = SPVTerms(
        management_fee_pct=Decimal(str(management_fee_pct)),
        carry_pct=Decimal(str(carry_pct)),
    )

    return cap_table, last_round, transaction, spv_terms


# ---------------------------------------------------------------------------
# Run the analysis
# ---------------------------------------------------------------------------

try:
    cap_table, last_round, transaction, spv_terms = build_deal()
    result = analyze_deal(
        cap_table=cap_table,
        last_round=last_round,
        transaction=transaction,
        spv_terms=spv_terms,
        exit_date=exit_date_input,
        exit_price_per_share=Decimal(str(exit_price)),
    )
except Exception as e:
    st.error(f"Could not build deal from inputs: {e}")
    st.stop()

if not result.validation.is_valid:
    st.error("This deal is invalid:")
    for err in result.validation.errors:
        st.write(f"- {err}")
    st.stop()

st.success("Deal is valid — all cap table and transaction checks passed.")

# ---------------------------------------------------------------------------
# Display results
# ---------------------------------------------------------------------------

col1, col2 = st.columns(2)

with col1:
    st.subheader("Seller Returns")
    sr = result.seller_returns
    st.metric("Gross proceeds", f"${sr.gross_proceeds:,.0f}")
    st.metric("Realized profit", f"${sr.realized_profit:,.0f}")
    st.metric("Realized multiple", f"{sr.realized_multiple:.2f}x")
    if sr.realized_xirr is not None:
        st.metric("Realized XIRR (annualised)", f"{sr.realized_xirr:.1%}")

    st.subheader("Ownership")
    o = result.ownership
    st.write(f"**{seller_name}** — before: {o.seller_ownership_before_pct:.2f}% → after: {o.seller_ownership_after_pct:.2f}%")
    st.write(f"**SPV** — after: {o.spv_ownership_after_pct:.2f}%")
    st.caption(f"Total shares outstanding unchanged: {o.cap_table_after.total_shares_outstanding:,} (share transfer, not dilution)")

with col2:
    st.subheader("Buyer Valuation")
    bv = result.buyer_valuation
    direction = "PREMIUM" if bv.premium_discount_pct > 0 else "DISCOUNT"
    st.metric(f"{direction} vs last round", f"{abs(bv.premium_discount_pct):.2f}%")
    st.write(f"Last round price: ${bv.last_round_price_per_share:,.2f}/share")
    st.write(f"Secondary price: ${bv.secondary_price_per_share:,.2f}/share")
    st.write(f"Implied valuation at secondary: ${bv.implied_company_valuation_at_secondary:,.0f}")

    st.subheader("SPV Waterfall")
    w = result.spv_waterfall
    st.metric("Net LP distribution", f"${w.net_lp_distribution:,.0f}")
    st.metric("Net MOIC", f"{w.net_moic:.2f}x")
    if w.net_irr is not None:
        st.metric("Net IRR", f"{w.net_irr:.1%}")

    st.markdown(f"""
    <div style="background-color:#16273e;border:1px solid #2a3d54;border-radius:10px;
                padding:14px 18px;margin-top:12px;animation:fadeIn 0.6s ease-out;">
        <div style="display:flex;justify-content:space-between;font-family:'Inter',sans-serif;
                    font-size:13px;color:#c3ccd8;padding:6px 0;border-bottom:0.5px solid #2a3d54;">
            <span>Gross investment</span><span>${w.gross_investment:,.0f}</span>
        </div>
        <div style="display:flex;justify-content:space-between;font-family:'Inter',sans-serif;
                    font-size:13px;color:#c3ccd8;padding:6px 0;border-bottom:0.5px solid #2a3d54;">
            <span>Management fee</span><span>${w.management_fee:,.0f}</span>
        </div>
        <div style="display:flex;justify-content:space-between;font-family:'Inter',sans-serif;
                    font-size:13px;color:#c3ccd8;padding:6px 0;border-bottom:0.5px solid #2a3d54;">
            <span>Carry</span><span>${w.carry:,.0f}</span>
        </div>
        <div style="display:flex;justify-content:space-between;font-family:'Inter',sans-serif;
                    font-size:13px;color:#c9a94d;padding:6px 0;">
            <span>Net LP distribution</span><span>${w.net_lp_distribution:,.0f}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

st.divider()

# ---------------------------------------------------------------------------
# AI Agent section
# ---------------------------------------------------------------------------

st.subheader("Ask the Deal Agent")
st.caption(
    "The agent answers questions by calling the same deterministic functions "
    "shown above — it never calculates a number itself. Requires Ollama "
    "running locally (see README.md)."
)

question = st.text_input("Ask a question about this deal", placeholder="e.g. What's the net IRR for LPs?")

if st.button("Ask") and question:
    try:
        from agent.current_deal import set_current_deal, CurrentDeal
        from agent.deal_agent import ask_agent

        set_current_deal(CurrentDeal(
            cap_table=cap_table,
            last_round=last_round,
            transaction=transaction,
            spv_terms=spv_terms,
            exit_date=exit_date_input,
            exit_price_per_share=Decimal(str(exit_price)),
        ))
        with st.spinner("Agent is working..."):
            answer = ask_agent(question)
        st.write(answer)
    except Exception as e:
        st.error(
            f"Agent unavailable: {e}\n\n"
            "Make sure Ollama is installed and running locally "
            "(https://ollama.com), and that you've pulled a model "
            "(e.g. `ollama pull llama3.1`)."
        )
