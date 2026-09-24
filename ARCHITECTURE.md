# Architecture

This document describes the system architecture: the component
structure, the data flow through a deal analysis, and, in particular
detail since it is the most novel part of the system, the LangChain
agentic workflow that powers "Ask the Deal Agent."

---

## 1. Component architecture

The system is layered so that the **deterministic financial core has
zero dependency on AI**. The UI and the AI agent are both thin clients
of the same `deal_service.analyze_deal()` function. Neither one
re-implements any financial logic.

```mermaid
graph TB
    subgraph "Presentation Layer"
        UI["app.py<br/>(Streamlit UI)"]
    end

    subgraph "Agentic Layer (LangChain)"
        AGENT["deal_agent.py<br/>AgentExecutor"]
        TOOLS["tools.py<br/>5 LangChain @tool functions"]
        DEAL["current_deal.py<br/>active deal in memory"]
        LLM(["Ollama<br/>local LLM<br/>(llama3.1)"])
    end

    subgraph "Orchestration"
        SVC["deal_service.py<br/>analyze_deal()"]
    end

    subgraph "Deterministic Core, zero AI dependency"
        VAL["validation/checks.py"]
        OWN["calculations/ownership.py"]
        SELL["calculations/seller_returns.py"]
        VALN["calculations/valuation.py"]
        SPV["calculations/spv_waterfall.py"]
        XIRR["calculations/xirr.py"]
        MODELS["domain/models.py<br/>CapTable, Holder, Transaction, SPVTerms"]
    end

    UI -->|"user inputs"| SVC
    UI -->|"question"| AGENT
    AGENT <-->|"reasons over tool descriptions"| LLM
    AGENT -->|"selected tool call"| TOOLS
    TOOLS -->|"reads active deal"| DEAL
    TOOLS -->|"calls"| SVC

    SVC --> VAL
    SVC --> OWN
    SVC --> SELL
    SVC --> VALN
    SVC --> SPV
    SELL --> XIRR
    SPV --> XIRR
    VAL --> MODELS
    OWN --> MODELS
    SELL --> MODELS
    VALN --> MODELS
    SPV --> MODELS

    style LLM fill:#16273e,stroke:#c9a94d,color:#f3f4f0
    style AGENT fill:#16273e,stroke:#c9a94d,color:#f3f4f0
    style TOOLS fill:#16273e,stroke:#c9a94d,color:#f3f4f0
    style SVC fill:#0f1b2d,stroke:#8ea3bd,color:#f3f4f0
```

**Key architectural rule:** every arrow flowing *into* the
"Deterministic Core" comes from `deal_service.py`. Nothing in the
Agentic Layer or Presentation Layer calls a calculation function
directly. They always go through the same orchestrator, so the UI,
the tests, and the AI agent are provably looking at the same numbers.

---

## 2. The LangChain agentic workflow (detail)

This is the sequence that runs when a user types a question into "Ask
the Deal Agent." It is the most important flow to understand, because
it's the mechanism that enforces the project's core rule: **the LLM
never calculates a financial figure. It only selects a tool and
explains that tool's already-correct output.**

```mermaid
sequenceDiagram
    actor User
    participant UI as Streamlit UI
    participant AE as LangChain<br/>AgentExecutor
    participant LLM as Ollama<br/>(llama3.1)
    participant Tool as Selected Tool<br/>(agent/tools.py)
    participant Deal as current_deal.py
    participant Engine as deal_service.py<br/>+ calculations/*

    User->>UI: Types question<br/>("What's the net IRR for LPs?")
    UI->>AE: ask_agent(question)
    AE->>LLM: System prompt + question +<br/>tool descriptions
    Note over LLM: LLM reasons: which of the<br/>5 tools answers this question?<br/>(get_seller_returns,<br/>get_buyer_valuation_comparison,<br/>get_spv_waterfall,<br/>get_ownership_summary,<br/>validate_current_deal)
    LLM-->>AE: Tool call decision:<br/>get_spv_waterfall()
    AE->>Tool: Invoke get_spv_waterfall()
    Tool->>Deal: get_current_deal()
    Deal-->>Tool: CurrentDeal (cap table,<br/>transaction, SPV terms, exit assumption)
    Tool->>Engine: analyze_deal(**deal_kwargs)
    Engine->>Engine: validate → ownership →<br/>seller_returns → valuation →<br/>spv_waterfall (XIRR, MOIC, carry)
    Engine-->>Tool: DealAnalysis<br/>(all figures, tested & correct)
    Tool-->>AE: Formatted text:<br/>"Net LP distribution: $27,600,000<br/>Net IRR: 14.5%..."
    AE->>LLM: Tool result
    Note over LLM: LLM explains the result<br/>in plain English.<br/>It does NOT recompute<br/>or alter any number
    LLM-->>AE: "The net IRR for LPs<br/>in this deal is 14.5%."
    AE-->>UI: Final answer
    UI-->>User: Displays answer +<br/>tool's raw output
```

**Why this design matters for a financial tool:** if the LLM were
allowed to reason about the numbers directly (rather than only
selecting a tool), a hallucinated or slightly-off figure could enter
the answer with no way to detect it. By constraining the LLM to
*tool selection and explanation only*, every number in the final
answer is guaranteed to trace back to a tested function in
`calculations/`, the same functions covered by the 19 tests in
`tests/`.

---

## 3. Data flow for a full deal analysis

This is the sequence for a single "Analyze Deal" pass. It is the same
whether it's triggered by the Streamlit UI on page load/input change,
or indirectly by an agent tool call.

```mermaid
sequenceDiagram
    participant Caller as UI or Agent Tool
    participant Service as deal_service.analyze_deal()
    participant Validation as validation/checks.py
    participant Ownership as calculations/ownership.py
    participant Seller as calculations/seller_returns.py
    participant Valuation as calculations/valuation.py
    participant Waterfall as calculations/spv_waterfall.py
    participant XIRR as calculations/xirr.py

    Caller->>Service: analyze_deal(cap_table, last_round,<br/>transaction, spv_terms, exit assumptions)
    Service->>Validation: validate_full_transaction()
    alt Deal invalid
        Validation-->>Service: ValidationResult(is_valid=False, errors)
        Service-->>Caller: DealAnalysis(validation=invalid,<br/>everything else=None)
    else Deal valid
        Validation-->>Service: ValidationResult(is_valid=True)
        Service->>Ownership: apply_secondary_transaction()
        Ownership-->>Service: OwnershipResult<br/>(before/after %, share conservation checked)
        Service->>Seller: calculate_seller_returns()
        Seller->>XIRR: xirr(cash_flows)
        XIRR-->>Seller: annualised rate
        Seller-->>Service: SellerReturns<br/>(proceeds, profit, multiple, XIRR)
        Service->>Valuation: calculate_buyer_valuation_comparison()
        Valuation-->>Service: BuyerValuationComparison<br/>(premium/discount %)
        Service->>Waterfall: calculate_spv_waterfall()
        Waterfall->>XIRR: xirr(gross & net cash flows)
        XIRR-->>Waterfall: gross & net IRR
        Waterfall-->>Service: SPVWaterfallResult<br/>(fee, carry, net MOIC/IRR)
        Service-->>Caller: DealAnalysis (complete, all fields populated)
    end
```

---

## 4. Why the deterministic core has no AI dependency

This isn't an accident. It is the central design constraint of the
project (see `ASSUMPTIONS.md` for the full reasoning). Concretely, it
means:

- `domain/`, `calculations/`, and `validation/` import nothing from
  `langchain`, `langchain_ollama`, or any AI library
- Every function in `calculations/` is a **pure function**: same
  inputs always produce the same outputs, with no hidden state,
  network calls, or randomness
- The 19 tests in `tests/` exercise this core directly, with no LLM
  involved. They would pass identically with Ollama uninstalled
- The AI agent (`agent/`) is architecturally a *client* of this core,
  in exactly the same sense that the Streamlit UI is a client of it
