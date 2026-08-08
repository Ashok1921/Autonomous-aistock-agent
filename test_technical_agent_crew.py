import os
from dotenv import load_dotenv
from crewai import Agent, Task, Crew, LLM
from agents.technical_agent import technical_analysis_tool

load_dotenv()

llm = LLM(
    model="gemini/gemini-2.5-flash",
    api_key=os.getenv("GEMINI_API_KEY")
)

technical_agent = Agent(
    role="Technical Analyst",
    goal="Analyze stock price data using technical indicators and report clear signals",
    backstory="You are an expert technical analyst specializing in Indian NSE/BSE stocks, skilled at reading RSI, MACD, and moving averages to spot trends.",
    tools=[technical_analysis_tool],
    llm=llm,
    verbose=True
)

task = Task(
    description="Run technical analysis on RELIANCE stock and summarize whether the signals look bullish, bearish, or neutral.",
    expected_output="A brief summary of RELIANCE's technical signals and an overall bullish/bearish/neutral assessment.",
    agent=technical_agent
)

crew = Crew(agents=[technical_agent], tasks=[task], verbose=True)
result = crew.kickoff()

print("\n--- FINAL RESULT ---")
print(result)