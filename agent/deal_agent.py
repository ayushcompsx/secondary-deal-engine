"""
The agent itself: a LangChain AgentExecutor, given access to the
deterministic tools in agent/tools.py.

TWO LLM BACKENDS SUPPORTED:
    1. Groq (cloud, free tier). Used automatically when a GROQ_API_KEY
       is available, either as an environment variable or (when running
       under Streamlit) in st.secrets. This is what powers the agent on
       the deployed Streamlit Cloud link, since Streamlit Cloud's
       servers cannot run a local model.
    2. Ollama (local, free, no API key). Used as the fallback for local
       development, so the agent still works with zero cloud dependency
       when you are just running `streamlit run app.py` on your laptop.

USAGE:
    from agent.current_deal import load_golden_example_deal
    from agent.deal_agent import ask_agent

    load_golden_example_deal()
    print(ask_agent("What's the net IRR for LPs in this deal?"))

REQUIREMENTS:
    For Groq (recommended for deployment):
        pip install langchain-groq
        export GROQ_API_KEY=gsk_...          (or set in Streamlit secrets)
    For Ollama (local dev, zero cost, zero API key):
        Install Ollama: https://ollama.com
        ollama pull llama3.1
        pip install langchain-ollama

The LLM is NEVER allowed to compute a financial figure itself. See the
system prompt below, which explicitly instructs it to always use a
tool rather than reasoning about numbers on its own. Every tool in
agent/tools.py calls straight through to the deterministic engine in
calculations/, so any number the agent states is traceable back to a
tested, verified calculation.
"""

from __future__ import annotations

import os

try:
    # LangChain 1.0+ moved AgentExecutor and create_tool_calling_agent
    # into langchain_classic, since the "legacy" agent API is being
    # superseded by langgraph-based agents. We deliberately use the
    # classic API here for simplicity in a small demo tool.
    from langchain_classic.agents import AgentExecutor, create_tool_calling_agent
except ImportError:
    # Older langchain (<1.0) has these directly in langchain.agents
    from langchain.agents import AgentExecutor, create_tool_calling_agent

from langchain_core.prompts import ChatPromptTemplate

from agent.tools import ALL_TOOLS


SYSTEM_PROMPT = """You are a financial analyst assistant for a secondary \
transaction and SPV deal. You have access to tools that read a deterministic, \
already-validated financial calculation engine.

CRITICAL RULES:
1. NEVER calculate or estimate a financial figure yourself. Always call the \
   appropriate tool to get real numbers.
2. If a question needs information from more than one tool (e.g. "summarise \
   this whole deal"), call all the relevant tools before answering.
3. If a tool reports the deal is invalid, explain that clearly rather than \
   guessing what the numbers might have been.
4. Explain figures in plain, clear English suitable for an investment \
   professional. Reference the actual numbers the tools returned, do not \
   round or restate them from memory once you've seen them.
5. If asked something the tools cannot answer (e.g. a hypothetical deal that \
   hasn't been loaded), say so explicitly rather than inventing a number.
"""


def _get_groq_api_key() -> str | None:
    """
    Looks for a Groq API key, in order of priority:
    1. The GROQ_API_KEY environment variable (works everywhere,
       including local terminal use and most deployment platforms)
    2. Streamlit secrets (st.secrets["GROQ_API_KEY"]), when running
       under Streamlit and a secrets.toml / Cloud secret is configured

    Returns None if neither is set, in which case the caller falls
    back to a local Ollama model instead.
    """
    key = os.environ.get("GROQ_API_KEY")
    if key:
        return key
    try:
        import streamlit as st
        return st.secrets.get("GROQ_API_KEY")
    except Exception:
        return None


def _build_llm(temperature: float = 0.0):
    """
    Builds the chat LLM to use, preferring Groq (cloud, works when
    deployed) and falling back to Ollama (local, zero cost, zero API
    key, works when developing on your own laptop).

    temperature=0.0 is deliberate for both backends: this agent's job
    is to retrieve and explain real numbers, not to be creative, so we
    want the most literal, deterministic behaviour the LLM can give us.
    """
    groq_key = _get_groq_api_key()
    if groq_key:
        from langchain_groq import ChatGroq
        # llama-3.3-70b-versatile was deprecated by Groq; openai/gpt-oss-120b
        # is their current recommended general-purpose model with tool-calling
        # support (see console.groq.com/docs/deprecations).
        return ChatGroq(
            model="openai/gpt-oss-120b",
            temperature=temperature,
            api_key=groq_key,
        )

    try:
        from langchain_ollama import ChatOllama
    except ImportError:
        from langchain_community.chat_models import ChatOllama
    return ChatOllama(model="llama3.1", temperature=temperature)


def build_agent_executor(temperature: float = 0.0) -> AgentExecutor:
    """
    Builds a LangChain tool-calling agent backed by whichever LLM
    backend is available (see _build_llm).
    """
    llm = _build_llm(temperature=temperature)

    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        ("human", "{input}"),
        ("placeholder", "{agent_scratchpad}"),
    ])

    agent = create_tool_calling_agent(llm, ALL_TOOLS, prompt)
    return AgentExecutor(agent=agent, tools=ALL_TOOLS, verbose=True)


def ask_agent(question: str) -> str:
    """Convenience one-shot function: ask a question, get an answer."""
    executor = build_agent_executor()
    result = executor.invoke({"input": question})
    return result["output"]


if __name__ == "__main__":
    from agent.current_deal import load_golden_example_deal

    load_golden_example_deal()

    backend = "Groq (cloud)" if _get_groq_api_key() else "Ollama (local)"
    print(f"=== Secondary & SPV Deal Agent (demo, backend: {backend}) ===")
    print("Loaded the golden example deal. Ask a question, or Ctrl+C to exit.\n")

    while True:
        try:
            question = input("You: ")
            if not question.strip():
                continue
            answer = ask_agent(question)
            print(f"\nAgent: {answer}\n")
        except KeyboardInterrupt:
            print("\nGoodbye.")
            break
