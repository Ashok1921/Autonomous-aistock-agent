import os
from dotenv import load_dotenv
from crewai import Agent, Task, Crew, LLM

load_dotenv()

llm = LLM(
    model="gemini/gemini-2.5-flash",
    api_key=os.getenv("GEMINI_API_KEY")
)

price_fetcher = Agent(
    role="Stock Price Fetcher",
    goal="Fetch and report the current price info for a given stock symbol",
    backstory="You are a financial data assistant that reports stock prices clearly and concisely.",
    llm=llm,
    verbose=True
)

task = Task(
    description="State that you are ready to fetch stock prices for Indian NSE/BSE stocks like TCS.NS and RELIANCE.NS. Just confirm you're operational.",
    expected_output="A short confirmation message that the agent is ready to fetch stock prices.",
    agent=price_fetcher
)

crew = Crew(
    agents=[price_fetcher],
    tasks=[task],
    verbose=True
)

result = crew.kickoff()
print("\n--- FINAL RESULT ---")
print(result)