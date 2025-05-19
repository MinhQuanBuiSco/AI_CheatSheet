import yfinance as yf


def search_stock_data(symbol: str) -> dict:
    stock = yf.Ticker(symbol)
    hist = stock.history(period="5d")
    return {"info": stock.info, "history": hist.tail(5).to_dict()}


def dummy_predict_price(history_data: dict) -> float:
    # Naive predictor: use average of last 5 days' close prices
    closes = history_data["Close"].values()
    return round(sum(closes) / len(closes), 2)
