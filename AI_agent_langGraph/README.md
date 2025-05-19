# 📈 Stock Prediction Agent with LangGraph & LangChain

A production-ready AI agent built using **LangGraph**, **LangChain**, and **OpenAI**, designed to search for stock information and intelligently predict stock prices. It demonstrates how to integrate custom tools, LLMs, and graph-based workflows for financial reasoning.

---

## 🚀 Features

- 🔍 **Stock Data Search** using Yahoo Finance
- 📊 **Price Prediction Agent** using historical averages (customizable)
- 🧠 **LangGraph Agent** with typed state transitions and tool chaining
- 🤖 **GPT-4o Compatible** (or any OpenAI-compatible LLM)
- 📦 Clean project structure with modular tools and logic

---

## 📁 Project Structure

```
.
├── agent.py          # LangGraph agent definition and orchestration
├── tools.py          # Tools for stock data search and prediction
├── model.py          # ML prediction logic (simple for now)
├── .env              # Secrets for OpenAI
```

---

## ⚙️ Setup

### 1. Install dependencies

Create a virtual environment and install packages:

```bash
uv venv --python 3.10
uv sync
```

### 2. Prepare `.env`

Create a `.env` file in the root directory:

```env
OPENAI_API_KEY=your_openai_key
```

---

## ▶️ Running the Agent

### Example (predict AAPL price):

```bash
python agent.py
```

> Output:
```
Predicted price for AAPL is $172.35
```

---

## 💡 How It Works

1. **Input**: A stock symbol (e.g., `AAPL`)
2. **Tool 1**: Fetch 5-day historical data using `yfinance`
3. **Tool 2**: Apply average-close prediction
4. **Agent Output**: Final summary of prediction + supporting details

---

## 📈 Extend It

You can replace the dummy prediction model in `model.py` with a real LSTM, XGBoost, or finetuned transformer model. LangGraph supports async tools, LangSmith logging, and external tool orchestration.

---

## 🔁 Sample Usage in Code

```python
from agent import run_agent

result = run_agent("TSLA")
print(result["summary"])
```

---

## 📄 License

MIT License – feel free to use this in your own trading agent experiments or integrate with dashboards and alerting systems.
