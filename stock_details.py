from flask import Blueprint, render_template, current_app
import yfinance as yf

stock_details = Blueprint("stock_details", __name__)

def fetch_stock_data(ticker):
    """Fetch stock details, financials, and price history."""
    try:
        conn = current_app.config["DB_POOL"].getconn()  # ✅ Use Flask db pool
        cur = conn.cursor()

        # ✅ Fetch stock details from DB
        cur.execute("SELECT * FROM Stock WHERE ticker = %s;", (ticker,))
        stock = cur.fetchone()
        # print(f"📌 Stock Data: {stock}")  # Debugging print

        if not stock:
            return None  # ✅ Stock not found

        # ✅ Fetch yearly financials
        cur.execute("SELECT * FROM Yearly_Financials WHERE stock_ticker = %s ORDER BY year DESC LIMIT 1;", (ticker,))
        yearly_financials = cur.fetchone()
        # print(f"📌 Yearly Financials: {yearly_financials}")  # Debugging print

        # ✅ Fetch latest quarterly financials
        cur.execute("SELECT * FROM Quarterly_Financials WHERE stock_ticker = %s ORDER BY quarter DESC LIMIT 1;", (ticker,))
        quarterly_financials = cur.fetchone()
        # print(f"📌 Quarterly Financials: {quarterly_financials}")  # Debugging print

        # ✅ Fetch market analysis
        cur.execute("SELECT * FROM Market_Analysis WHERE stock_ticker = %s;", (ticker,))
        market_analysis = cur.fetchone()
        # print(f"📌 Market Analysis: {market_analysis}")  # Debugging print

        cur.close()
        current_app.config["DB_POOL"].putconn(conn)  # ✅ Return connection to pool

        # ✅ Fetch real-time stock data from Yahoo Finance
        stock_obj = yf.Ticker(ticker)
        hist = stock_obj.history(period="6mo")  # Fetch past 6 months data

        chart_data = {
            "dates": hist.index.strftime("%Y-%m-%d").tolist(),
            "prices": hist["Close"].tolist()
        }
        # print(f"📊 Chart Data: {chart_data}")  # Debugging print

        # ✅ Convert tuples to dictionaries before passing to template
        return {
            "stock": {
                "ticker": stock[0],
                "name": stock[1],
                "price": stock[2],
                "high_52": stock[3],
                "low_52": stock[4],
            },
            "yearly_financials": {
                "year": yearly_financials[1] if yearly_financials else None,
                "eps_growth": yearly_financials[2] if yearly_financials else None,
                "revenue_growth": yearly_financials[3] if yearly_financials else None,
                "profit": yearly_financials[4] if yearly_financials else None,
                "earnings": yearly_financials[5] if yearly_financials else None,
            } if yearly_financials else None,
            "quarterly_financials": {
                "quarter": quarterly_financials[1] if quarterly_financials else None,
                "eps_growth": quarterly_financials[2] if quarterly_financials else None,
                "revenue_growth": quarterly_financials[3] if quarterly_financials else None,
                "profit": quarterly_financials[4] if quarterly_financials else None,
                "earnings": quarterly_financials[5] if quarterly_financials else None,
            } if quarterly_financials else None,
            "market_analysis": {
                "pe_ratio": market_analysis[1] if market_analysis else None,
                "dividend_yield": market_analysis[2] if market_analysis else None,
                "market_cap": market_analysis[3] if market_analysis else None,
                "volume": market_analysis[4] if market_analysis else None,
            } if market_analysis else None,
            "chart_data": chart_data
        }

    except Exception as e:
        print(f"❌ Database Error: {e}")
        return None  # Return None if there's an error


@stock_details.route("/stock/<ticker>")
def stock_page(ticker):
    """Render stock details page."""
    stock_data = fetch_stock_data(ticker)  # ✅ No async needed anymore
    if not stock_data or not stock_data["stock"]:
        return "Stock not found", 404  # Return 404 if stock does not exist
    return render_template("stock_details.html", **stock_data)
