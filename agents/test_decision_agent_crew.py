"""
Crew test for the Decision Agent.

Wires decision_tool into a real CrewAI Agent + Task + Crew (Gemini 2.5 Flash),
matching the pattern of test_technical_agent_crew.py / test_fundamental_agent_crew.py
/ test_prediction_agent_crew.py.

The agent's job is NOT to re-decide anything — the verdict, conviction, stop-loss,
and target-price are already fixed by the hard-coded risk-rule engine. The agent's
job is to explain that decision clearly and honestly, including when data is thin
or a risk flag capped the conviction.

Run as: python -m agents.test_decision_agent_crew [SYMBOL]
(defaults to RELIANCE, since it exercises both a real verdict and a risk-flag override)
"""

import sys
from crewai import Agent, Task, Crew, LLM

from agents.decision_agent import decision_tool

llm = LLM(model="gemini/gemini-2.5-flash")

decision_explainer = Agent(
    role="Investment Decision Analyst",
    goal=(
        "Explain the system's verdict for a stock clearly and honestly, using only "
        "the signals, weights, and risk flags provided by the Decision Analysis Tool. "
        "Never override the verdict, conviction, stop-loss, or target-price — your job "
        "is to explain the decision, not remake it."
    ),
    backstory=(
        "You are a disciplined analyst who values honesty over optimism. You know that "
        "the Prediction Agent's signal is roughly coinflip-accurate and must never be "
        "treated as a strong reason on its own. You know that when data is missing or "
        "a risk flag capped the conviction, that caveat matters as much as the verdict "
        "itself, and it must be stated plainly, not buried or softened. You never claim "
        "more confidence than the conviction score supports, and you never invent a "
        "reason that isn't in the tool output."
    ),
    tools=[decision_tool],
    llm=llm,
    verbose=True,
)

decision_task = Task(
    description=(
        "Get the current investment decision for {symbol} using the Decision Analysis Tool. "
        "Then write a short, plain-English explanation for a retail investor that covers:\n"
        "1. The verdict and what it means practically\n"
        "2. The 1-2 signals that drove the verdict the most (by weight and score)\n"
        "3. Any risk flags — state them directly, don't soften them\n"
        "4. The stop-loss and target-price if given, or state clearly that none apply "
        "because the verdict is HOLD or data was insufficient\n"
        "5. An explicit statement of how much conviction the system has in this call, "
        "using the conviction score itself, not vague language like 'fairly confident'\n\n"
        "Do not add optimism, hedge softer than the data supports, or suggest a different "
        "action than the verdict. If signals are missing or stale, say so plainly."
    ),
    expected_output=(
        "A short (under 200 words) plain-English explanation of the decision for {symbol}, "
        "covering verdict, key drivers, risk flags, stop-loss/target-price (or their absence), "
        "and an honest statement of conviction."
    ),
    agent=decision_explainer,
)

crew = Crew(
    agents=[decision_explainer],
    tasks=[decision_task],
    verbose=True,
)


if __name__ == "__main__":
    symbol = sys.argv[1] if len(sys.argv) > 1 else "RELIANCE"
    result = crew.kickoff(inputs={"symbol": symbol})
    print("\n--- FINAL OUTPUT ---\n")
    print(result)