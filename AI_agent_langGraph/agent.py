import os
from typing import Any, TypedDict

from dotenv import load_dotenv
from langchain.agents import AgentExecutor, Tool, initialize_agent
from langchain.chat_models import ChatOpenAI
from langchain.schema import SystemMessage
from langgraph.graph import END, StateGraph
from tools import dummy_predict_price, search_stock_data


class StockAgentState(TypedDict):
    symbol: str
    result: dict


load_dotenv()
llm = ChatOpenAI(model="gpt-4", temperature=0)

# Define tools
tools = [
    Tool.from_function(
        func=search_stock_data,
        name="SearchStock",
        description="Fetch stock data for a given symbol (e.g., AAPL)",
    ),
    Tool.from_function(
        func=dummy_predict_price,
        name="PredictPrice",
        description="Predict future stock price using last 5-day history",
    ),
]


# Define LangGraph steps
def agent_step(state):
    symbol = state["symbol"]
    data = search_stock_data(symbol)
    prediction = dummy_predict_price(data["history"])

    return {
        "symbol": symbol,
        "result": {
            "summary": f"Predicted price for {symbol} is ${prediction}",
            "details": data,
        },
    }


# Define LangGraph state
graph = StateGraph(StockAgentState)
graph.add_node("predictor", agent_step)
graph.set_entry_point("predictor")
graph.set_finish_point("predictor")
runnable = graph.compile()


# Entry function
def run_agent(symbol):
    result = runnable.invoke({"symbol": symbol})
    return result["result"]


if __name__ == "__main__":
    result = run_agent("AAPL")
    print(result["summary"])
    # Optionally save results or pass to frontend
