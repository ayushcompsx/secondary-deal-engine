# Secondary & SPV Deal Engine

![Tests](https://img.shields.io/badge/tests-19%20passing-brightgreen)
![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![LangChain](https://img.shields.io/badge/agent-LangChain%20%2B%20Ollama-black)
![License](https://img.shields.io/badge/license-MIT-lightgrey)

A deterministic financial engine for modelling late-stage secondary
transactions wrapped inside an SPV. It models the exact deal type described in
Chelsea Square Capital's "What We Do": *"late-stage secondaries, SPVs
and co-GP vehicles, offered to a small circle of aligned capital."*

A thin AI agent sits on top of the engine to answer plain-English
questions, but **the agent never calculates anything itself**. Every
number it states comes from a tested, hand-verified deterministic
function. See `agent/tools.py` and `ASSUMPTIONS.md` for why this
separation matters.

---

---

## What it calculates

Given a company's cap table, its last funding round, a proposed
secondary sale, and a set of SPV terms (management fee, carry), the
engine calculates:

- **Seller side**: gross proceeds, cost basis, realized profit,
  realized multiple, and realized XIRR (time-aware annualised return)
- **Ownership**: cap table before and after the transaction, with
  share-conservation enforced (a secondary sale transfers existing
  shares, it never creates new ones)
- **Buyer side**: whether the secondary price is a premium or
  discount versus the last funding round
- **SPV / LP side**: management fee, carried interest, net
  distribution, gross and net MOIC, gross and net IRR

## Project structure

```
domain/models.py            Typed, validated data models (CapTable, Holder,
                             SecondaryTransaction, SPVTerms, ...)
calculations/xirr.py         Date-aware IRR (XIRR), implemented from scratch
calculations/ownership.py    Share transfer + conservation checks
calculations/seller_returns.py   Seller proceeds, profit, multiple, XIRR
calculations/valuation.py    Buyer premium/discount vs last round
calculations/spv_waterfall.py    Fee, carry, net LP returns
calculations/deal_service.py     Orchestrates the full analysis end-to-end
validation/checks.py         Cross-object validation (e.g. can't sell more
                             shares than you own)
agent/tools.py               LangChain tools wrapping the engine
agent/current_deal.py        Holds the active deal for the agent to read
agent/deal_agent.py          The LangChain AgentExecutor (uses local Ollama)
app.py                       Streamlit UI
tests/                       19 tests, including one full hand-verified
                             "golden" transaction (see FINANCIAL_MODEL.md)
```

## Running it

### 1. Run the tests (proves the maths is correct)

```bash
pip install -r requirements.txt
python3 -m pytest tests/ -v
```

You should see `19 passed`.

### 2. Run the UI

```bash
streamlit run app.py
```

Opens a browser dashboard where you can adjust every input (cap
table, secondary price, SPV terms, exit assumptions) and see the full
breakdown update live.

### 3. Use the AI agent

The agent requires a free local LLM via [Ollama](https://ollama.com):

```bash
# Install Ollama, then:
ollama pull llama3.1
```

Then either use the UI's "Ask the Deal Agent" box, or run the agent
directly from the terminal:

```bash
python3 -m agent.deal_agent
```

## Documentation

- **`ARCHITECTURE.md`**: component diagram and sequence diagrams
  (UML-style), with detailed coverage of the LangChain agentic
  workflow, covering how the LLM selects a tool and why it never calculates
  a figure itself
- **`FINANCIAL_MODEL.md`**: every formula used, with the hand-worked
  golden example
- **`ASSUMPTIONS.md`**: every explicit assumption made (SPV fee
  treatment, waterfall structure, valuation basis) and why

## Design principle

The deterministic engine (`domain/`, `calculations/`, `validation/`)
has zero dependency on AI, the internet, or any external service.
it's pure, testable Python. The AI agent is an optional layer on top
that retrieves and explains results; it is never the source of a
financial figure. This mirrors how a real investment or fund
administration team would want AI used: to speed up explanation and
retrieval, never to replace the calculation itself.
