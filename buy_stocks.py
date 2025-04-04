import yfinance as yf
from flask import Blueprint, render_template, request, jsonify, current_app
from flask_login import login_required

buy_stocks = Blueprint("buy_stocks", __name__)

def fetch_data(query, params=None):
    """Fetch data from PostgreSQL using connection pooling."""
    conn = current_app.config["DB_POOL"].getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(query, params or ())
            column_names = [desc[0] for desc in cur.description]
            return [dict(zip(column_names, row)) for row in cur.fetchall()]
    except Exception as e:
        print(f"❌ Database Error: {e}")
        return []
    finally:
        current_app.config["DB_POOL"].putconn(conn)

@buy_stocks.route("/buy-stocks")
@login_required
def buy_stocks_page():
    """Fetch available stocks and render the buy stocks page."""
    query = "SELECT ticker, name, price, high_52, low_52 FROM Stock;"
    stocks = fetch_data(query)
    return render_template("buy_stocks.html", stocks=stocks)

@buy_stocks.route("/high-stocks", methods=["GET"])
def high_stocks():
    """Fetch and return stocks where 52W high is at least 2.1x the low."""
    query = "SELECT * FROM get_high_stocks();"
    stocks = fetch_data(query)
    return jsonify(stocks)

@buy_stocks.route("/low-stocks", methods=["GET"])
def low_stocks():
    """Fetch and return stocks where 52W low has not changed."""
    query = "SELECT * FROM get_low_stocks();"
    stocks = fetch_data(query)
    return jsonify(stocks)

@buy_stocks.route("/filter-stocks", methods=["POST"])
def filter_stocks():
    """Filter stocks based on user-provided criteria."""
    data = request.json
    min_eps = data.get("min_eps", 0)
    max_pe = data.get("max_pe", 100)
    # Adjust the stored function as needed; here we pass min_eps and max_pe.
    query = "SELECT * FROM filter_stocks(%s, %s);"
    stocks = fetch_data(query, (min_eps, max_pe))
    return jsonify(stocks)

@buy_stocks.route("/top-movers", methods=["GET"])
def top_movers():
    """
    Fetch and return the top 5 stocks with the highest 7-day percentage change.
    This endpoint uses the Stock table for current price and yfinance for historical data.
    """
    query = "SELECT ticker, name, price FROM Stock;"
    stocks = fetch_data(query)
    top_gainers = []
    top_losers = []
    for stock in stocks:
        ticker = stock["ticker"]
        name = stock["name"]
        try:
            latest_price = float(stock["price"])
        except Exception as e:
            print(f"❌ Error converting price for {ticker}: {e}")
            continue
        try:
            # Fetch 7-day-old price using yfinance
            stock_data = yf.Ticker(ticker)
            history = stock_data.history(period="7d")
            if len(history) < 2:
                continue  # Not enough data
            old_price = history.iloc[0]["Close"]
            percentage_change = round(((latest_price - old_price) / old_price) * 100, 2)
            stock_info = {"name": name, "percentage_change": percentage_change}
            if percentage_change > 0:
                top_gainers.append(stock_info)
            else:
                top_losers.append(stock_info)
        except Exception as e:
            print(f"❌ Error fetching data for {ticker}: {e}")
    top_gainers = sorted(top_gainers, key=lambda x: x["percentage_change"], reverse=True)[:5]
    top_losers = sorted(top_losers, key=lambda x: x["percentage_change"])[:5]
    return jsonify({"gainers": top_gainers, "losers": top_losers})

@buy_stocks.route("/highest-eps-growth", methods=["GET"])
def highest_eps_growth():
    """
    Fetch stocks with the highest EPS growth over the past year.
    Uses the Yearly_Financials table.
    """
    query = """
    SELECT s.ticker, s.name, yf.eps_growth
    FROM Stock s
    JOIN Yearly_Financials yf ON s.ticker = yf.stock_ticker
    WHERE yf.year = 2024
    ORDER BY yf.eps_growth DESC
    LIMIT 5;
    """
    data = fetch_data(query)
    return jsonify(data)

@buy_stocks.route("/undervalued-stocks", methods=["GET"])
def undervalued_stocks():
    """
    Fetch undervalued stocks based on low P/E ratio & high EPS growth.
    Uses Market_Analysis and Yearly_Financials.
    """
    query = """
    SELECT s.ticker, s.name, ma.pe_ratio, yf.eps_growth
    FROM Stock s
    JOIN Market_Analysis ma ON s.ticker = ma.stock_ticker
    JOIN Yearly_Financials yf ON s.ticker = yf.stock_ticker
    WHERE ma.pe_ratio < 150 
      AND yf.eps_growth > 0.1
      AND yf.year = 2024
    ORDER BY yf.eps_growth DESC;
    """
    data = fetch_data(query)
    return jsonify(data)

@buy_stocks.route("/most-traded-stocks", methods=["GET"])
def most_traded_stocks():
    """
    Find stocks with the highest trading volume.
    Uses the Market_Analysis table.
    """
    query = """
    SELECT s.ticker, s.name, ma.volume AS total_volume
    FROM Stock s
    JOIN Market_Analysis ma ON s.ticker = ma.stock_ticker
    ORDER BY ma.volume DESC
    LIMIT 10;
    """
    data = fetch_data(query)
    return jsonify(data)
