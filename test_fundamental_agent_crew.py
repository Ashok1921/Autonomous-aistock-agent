"""
Crew test for the Fundamental Agent — same shape as test_technical_agent_crew.py.
Spins up a real Agent + Task + Crew, has the agent call the
Fundamental Analysis Tool, and prints its reasoning/assessment.
"""

from crewai import Agent, Task, Crew
from crewai import LLM

from agents.fundamental_agent import fundamental_analysis_tool

llm = LLM(model="gemini/gemini-2.5-flash")

fundamental_analyst = Agent(
    role="Fundamental Analyst",
    goal="Evaluate a company's financial health and valuation using fundamental ratios",
    backstory=(
        "You are a seasoned equity analyst who specializes in fundamental analysis. "
        "You read P/E, EPS, ROE, debt-to-equity, margins, and growth figures and turn "
        "them into a clear, well-reasoned view on whether a stock looks fundamentally "
        "strong, fairly valued, overvalued, or risky."
    ),
    tools=[fundamental_analysis_tool],
    llm=llm,
    verbose=True,
)

analyze_task = Task(
    description=(
        "Fetch the fundamental data for the stock symbol {symbol} using the "
        "Fundamental Analysis Tool. Then assess the company's financial health "
        "covering: valuation (P/E, forward P/E, PEG), profitability (ROE, ROA, "
        "profit margin), leverage/liquidity (debt-to-equity, current ratio), and "
        "growth (revenue growth). Conclude with an overall fundamental "
        "assessment: strong / neutral / weak, with a one-sentence justification."
    ),
    expected_output=(
        "A short structured summary covering valuation, profitability, leverage, "
        "and growth, ending with a clear strong/neutral/weak verdict and why."
    ),
    agent=fundamental_analyst,
)

crew = Crew(
    agents=[fundamental_analyst],
    tasks=[analyze_task],
    verbose=True,
)

if __name__ == "__main__":
    result = crew.kickoff(inputs={"symbol": "RELIANCE"})
    print("\n" + "=" * 60)
    print("FUNDAMENTAL ANALYSIS RESULT")
    print("=" * 60)
    print(result)