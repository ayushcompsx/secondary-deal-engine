"""
The agent itself: a LangChain AgentExecutor backed by a local Ollama
model, given access to the deterministic tools in agent/tools.py.

USAGE:
    from agent.current_deal import load_golden_example_deal
    from agent.deal_agent import ask_agent

    load_golden_example_deal()
    print(ask_agent("What's the net IRR for LPs in this deal?"))

REQUIREMENTS (all free):
    1. Install Ollama: https://ollama.com
    2. Pull a model:   ollama pull llama3.1
       (or qwen2.5, mistral — any tool-calling-capable model)
    3. pip install langchain langchain-community

The LLM is NEVER allowed to compute a financial figure itself — see
the system prompt below, which explicitly instructs it to always use
a tool rather than reasoning about numbers on its own. Every tool in
agent/tools.py calls straight through to the deterministic engine in
calculations/, so any number the agent states is traceable back to a
tested, verified calculation.
"""

from __future__ import annotations

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
try:
    # Preferred: dedicated langchain-ollama package (langchain-community's
    # chat model integrations, including Ollama, are being sunset in favor
    # of standalone integration packages).
    from langchain_ollama import ChatOllama
except ImportError:
    # Fallback for older environments still on langchain-community.
    from langchain_community.chat_models import ChatOllama

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
   professional. Reference the actual numbers the tools returned — do not \
   round or restate them from memory once you've seen them.
5. If asked something the tools cannot answer (e.g. a hypothetical deal that \
   hasn't been loaded), say so explicitly rather than inventing a number.
"""


def build_agent_executor(model_name: str = "llama3.1", temperature: float = 0.0) -> AgentExecutor:
    """
    Builds a LangChain tool-calling agent backed by a local Ollama model.
    temperature=0.0 is deliberate: this agent's job is to retrieve and
    explain real numbers, not to be creative, so we want the most
    deterministic, literal behaviour the LLM can give us.
    """
    llm = ChatOllama(model=model_name, temperature=temperature)

    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        ("human", "{input}"),
        ("placeholder", "{agent_scratchpad}"),
    ])

    agent = create_tool_calling_agent(llm, ALL_TOOLS, prompt)
    return AgentExecutor(agent=agent, tools=ALL_TOOLS, verbose=True)


def ask_agent(question: str, model_name: str = "llama3.1") -> str:
    """Convenience one-shot function: ask a question, get an answer."""
    executor = build_agent_executor(model_name=model_name)
    result = executor.invoke({"input": question})
    return result["output"]


if __name__ == "__main__":
    from agent.current_deal import load_golden_example_deal

    load_golden_example_deal()

    print("=== Secondary & SPV Deal Agent (demo) ===")
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
