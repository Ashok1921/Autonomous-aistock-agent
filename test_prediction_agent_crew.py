"""
Crew test for the Prediction Agent — same shape as
test_technical_agent_crew.py / test_fundamental_agent_crew.py.
Spins up a real Agent + Task + Crew, has the agent call the Prediction Tool,
and prints its reasoning/assessment — including how it should treat low
confidence, rather than overstating the prediction.
"""

from crewai import Agent, Task, Crew
from crewai import LLM

from agents.prediction_agent import prediction_tool

llm = LLM(model="gemini/gemini-2.5-flash")

prediction_analyst = Agent(
    role="Quantitative Prediction Analyst",
    goal="Interpret a model-generated stock price prediction honestly, including its confidence level",
    backstory=(
        "You are a quantitative analyst who reviews machine-learning-generated "
        "stock predictions. You understand that short-term price predictions are "
        "inherently noisy, and you always weigh the confidence score before "
        "drawing conclusions. You never overstate a low-confidence prediction as "
        "a strong signal."
    ),
    tools=[prediction_tool],
    llm=llm,
    verbose=True,
)

analyze_task = Task(
    description=(
        "Get the next-day prediction for stock symbol {symbol} using the "
        "Prediction Tool. Report the predicted direction and % change, then "
        "explicitly interpret the confidence score: if confidence is below 0.55, "
        "state clearly that the model shows little to no real predictive edge "
        "and the prediction should not be treated as a strong signal. If "
        "confidence is 0.55 or higher, describe it as a mild edge. Do not "
        "exaggerate certainty regardless of the confidence value."
    ),
    expected_output=(
        "A short, honest interpretation of the prediction: direction, % change, "
        "and a plain-language read on how much weight the confidence score "
        "actually justifies."
    ),
    agent=prediction_analyst,
)

crew = Crew(
    agents=[prediction_analyst],
    tasks=[analyze_task],
    verbose=True,
)

if __name__ == "__main__":
    result = crew.kickoff(inputs={"symbol": "TCS"})
    print("\n" + "=" * 60)
    print("PREDICTION ANALYSIS RESULT")
    print("=" * 60)
    print(result)