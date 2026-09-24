# Assumptions

Every material assumption in this engine is documented here, and also
inline in the relevant module's docstring. Nothing below is a silent
default — each one was a deliberate choice, made explicit so it can be
challenged or changed.

## 1. SPV management fee treatment

**Assumption**: the management fee is charged **upfront, on gross
investment**, and modelled as an *additional* LP cost on top of the
investment (i.e. `lp_total_contribution = gross_investment +
management_fee`), rather than being deducted *from* committed capital
before it's invested.

**Why this matters**: an alternative, equally common structure deducts
the fee from committed capital (so less money is actually invested).
That alternative would change `gross_investment` itself, and therefore
every downstream MOIC/IRR figure. This engine's choice is documented
so it can be swapped in `calculations/spv_waterfall.py` without
touching any other module.

## 2. Carry / waterfall structure

**Assumption**: deal-by-deal, American-style carry, **no preferred
return / hurdle rate**, applied to profit only
(`exit_gross_proceeds − gross_investment`).

**Why this matters**: many funds use a European (whole-fund) waterfall
with a preferred return and GP catch-up, which produces different
(usually more LP-favourable) net numbers on any single deal. This
engine deliberately implements the simplest standard structure for a
single-asset SPV as v1, with the explicit intention that the waterfall
module (`calculations/spv_waterfall.py`) can be swapped for a more
complex structure later without touching seller_returns.py,
ownership.py, or valuation.py.

## 3. Valuation basis (fully diluted)

**Assumption**: `LastRoundValuation.post_money_valuation` and
`fully_diluted_shares` are both already on a consistent, fully-diluted
basis — i.e. the valuation already reflects the option pool and all
share classes.

**Why this matters**: if the source data is NOT on this consistent
basis (e.g. valuation includes the option pool but the share count
doesn't), `last_round_price` will be understated, making every
premium/discount calculation misleading. This is flagged explicitly in
`calculations/valuation.py` rather than silently assumed away.

## 4. Realized multiple scope

**Assumption**: `realized_multiple` (and the TVPI-style ratio it
represents) is calculated **only on the shares actually sold** in this
transaction. It does not include any unrealized value of shares the
seller retains after the sale.

**Why this matters**: blending realized and unrealized value into one
number is a common source of misleading TVPI figures. If a retained
position's unrealized value needs to be shown, it should be a
*separate*, clearly-labelled figure — this is a known extension point,
not built in v1.

## 5. Cash flow validation for XIRR

**Assumption**: XIRR requires at least one negative (outflow) and one
positive (inflow) cash flow, on at least two distinct dates. Same-day
investment-and-exit, or all-outflow / all-inflow cash flow sets, are
explicitly rejected (`XIRRError`) rather than returning a
misleading number like 0% or an undefined infinite rate.

## 6. Single "current deal" in the agent layer

**Assumption**: `agent/current_deal.py` holds one deal in a simple
module-level variable, not keyed by session or user.

**Why this matters**: this is intentionally sufficient for a
single-user demo tool. A multi-user production version would need to
key the current deal by session ID (or pass it explicitly through the
agent's tool-calling context) instead of using a shared global — this
is a known, deliberate simplification for v1, not an oversight.

## 7. What's explicitly out of scope for v1

The following are real features a production version of this tool
would need, deliberately excluded here to hit a tight deadline with a
correct, well-tested core rather than a broken, ambitious one:

- Persistence / database (every run is in-memory only)
- Multiple SPV holders / partial LP allocations
- Primary issuance / dilution modelling
- European waterfall, preferred return, GP catch-up, clawback
- Multi-tenant / multi-user session handling
- Document extraction (reading cap tables from PDFs/Excel automatically)
- Cloud deployment, authentication, audit logging infrastructure

Each of these is a natural, clearly-scoped extension point on top of
the existing architecture (see the module boundaries in README.md),
not a redesign.
