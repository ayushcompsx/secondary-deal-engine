# Financial Model

## 1. Secondary transaction vs primary issuance

A **secondary transaction** transfers *existing* shares from a seller
to a buyer. It does **not** create new shares. `total_shares_outstanding`
is identical before and after. This is enforced as a hard invariant in
`calculations/ownership.py`. If a code change ever caused share
creation during a "secondary" transfer, the relevant test would fail
immediately.

This is distinct from a **primary issuance** (a funding round), which
does create new shares and dilutes existing holders. This engine only
models secondaries; primary issuance is out of scope for v1.

## 2. Valuation

Last round price per share:

```
last_round_price = post_money_valuation / fully_diluted_shares
```

**Assumption**: this assumes `post_money_valuation` and
`fully_diluted_shares` are both already on a consistent, fully-diluted
basis (option pool and all share classes included). If the source data
isn't consistent on this basis, the comparison below will be
misleading. See ASSUMPTIONS.md.

## 3. Premium / discount

```
premium_discount_pct = (secondary_price - last_round_price) / last_round_price × 100
```

Positive = premium (buyer pays more than the last round implied).
Negative = discount.

## 4. Seller returns

```
gross_proceeds        = shares_sold × secondary_price_per_share
cost_basis_of_shares   = shares_sold × seller_cost_basis_per_share
realized_profit        = gross_proceeds − cost_basis_of_shares
realized_multiple      = gross_proceeds / cost_basis_of_shares
```

`realized_multiple` here is calculated **only on the shares sold**.
it deliberately does not blend in any unrealized value from shares the
seller retains, per the project's rule against conflating realized and
unrealized value.

## 5. XIRR (date-aware IRR)

XIRR solves for the rate `r` such that:

```
Σ  cash_flow_i / (1 + r) ^ (days_i / 365)   =   0
```

where `days_i` is the number of days between `cash_flow_i`'s date and
the first cash flow's date. Implemented from scratch in
`calculations/xirr.py` using Newton's method with a bisection fallback
for robustness, with no external financial library required.

**Why XIRR and not plain IRR**: plain IRR assumes evenly-spaced
periodic cash flows. Real secondary transactions and SPV exits happen
on arbitrary dates, so XIRR (which is date-aware) is the correct
methodology.

## 6. SPV waterfall

**Structure chosen for v1** (documented in full in
`calculations/spv_waterfall.py`'s module docstring): deal-by-deal,
American-style, **no preferred return / hurdle**. This is the simplest
standard structure for a single-asset secondary SPV.

```
management_fee        = gross_investment × management_fee_pct   (charged upfront)
lp_total_contribution  = gross_investment + management_fee
profit                 = max(0, exit_gross_proceeds − gross_investment)
carry                  = profit × carry_pct
net_lp_distribution    = exit_gross_proceeds − carry
gross_moic              = exit_gross_proceeds / gross_investment
net_moic                = net_lp_distribution / lp_total_contribution
```

Gross IRR uses cash flows `[-gross_investment, +exit_gross_proceeds]`.
Net IRR uses cash flows `[-lp_total_contribution, +net_lp_distribution]`.

**Not built in v1** (explicit scope decision, see ASSUMPTIONS.md):
European/whole-fund waterfalls, preferred return + GP catch-up,
clawback provisions.

---

## Golden worked example

This exact scenario is encoded as a regression test in
`tests/test_golden_transaction.py`. Every number below was calculated
by hand before any code was written.

**Company**: TechCo
**Last round**: $1,000,000,000 post-money, 100,000,000 fully diluted
shares → **$10.00/share**

**Seller**: Investor A
- Owns 5,000,000 shares (5% of 100,000,000 total)
- Acquired 2022-01-01 at $4.00/share ($20,000,000 total cost)

**Secondary transaction (2024-01-01)**:
- Sells 2,000,000 of their 5,000,000 shares
- Price: $9.00/share (a 10% discount to the $10.00 last round price)

**Seller-side results**:
| Metric | Value |
|---|---|
| Gross proceeds | $18,000,000 |
| Cost basis of shares sold | $8,000,000 |
| Realized profit | $10,000,000 |
| Realized multiple | 2.25x |
| Realized XIRR (exactly 2 years) | 50.0% |

**Ownership results**:
| Holder | Before | After |
|---|---|---|
| Investor A (seller) | 5.00% | 3.00% |
| SPV (buyer) | 0.00% | 2.00% |
| Total shares outstanding | 100,000,000 | 100,000,000 (unchanged) |

**Buyer valuation**:
| Metric | Value |
|---|---|
| Last round price | $10.00/share |
| Secondary price | $9.00/share |
| Premium/discount | -10.00% (a discount) |

**SPV terms**: 2% management fee, 20% carry, exit assumed 2027-01-01
at $15.00/share

**SPV results**:
| Metric | Value |
|---|---|
| Gross investment | $18,000,000 |
| Management fee | $360,000 |
| LP total contribution | $18,360,000 |
| Exit gross proceeds | $30,000,000 |
| Profit | $12,000,000 |
| Carry | $2,400,000 |
| Net LP distribution | $27,600,000 |
| Gross MOIC | 1.667x |
| Net MOIC | 1.503x |
| Gross IRR | ~18.6% |
| Net IRR | ~15.0% |
