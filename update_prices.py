import psycopg2
import yfinance as yf
from app import app  # Import Flask app to access DB_POOL

def update_stock_prices():
    """Fetch latest stock data and update the database."""
    conn = app.config["DB_POOL"].getconn()
    cur = conn.cursor()

    # Fetch tickers from the Stock table
    cur.execute("SELECT ticker FROM Stock;")
    tickers = [row[0] for row in cur.fetchall()]

    if not tickers:
        print("No stocks found.")
        cur.close()
        app.config["DB_POOL"].putconn(conn)
        return

    print(f"Fetching prices and financials for: {tickers}")

    for ticker in tickers:
        try:
            stock = yf.Ticker(ticker)

            # Fetch real-time stock data
            stock_data = stock.history(period="1d")
            if stock_data.empty:
                print(f"⚠️ No data found for {ticker}. Skipping update.")
                continue

            latest_price = float(stock_data["Close"].iloc[-1])
            high_52 = float(stock.info.get("fiftyTwoWeekHigh", 0))
            low_52 = float(stock.info.get("fiftyTwoWeekLow", 0))
            stock_name = stock.info.get("longName", "Unknown")

            print(f"✅ {ticker} Price: {latest_price}, 52W High: {high_52}, 52W Low: {low_52}")

            # Update Stock Table
            cur.execute(
                """INSERT INTO Stock (ticker, name, price, high_52, low_52)
                   VALUES (%s, %s, %s, %s, %s)
                   ON CONFLICT (ticker) 
                   DO UPDATE SET 
                       name = EXCLUDED.name,
                       price = EXCLUDED.price, 
                       high_52 = EXCLUDED.high_52, 
                       low_52 = EXCLUDED.low_52;""",
                (ticker, stock_name, latest_price, high_52, low_52)
            )

            # Fetch and update Market Analysis Table
            pe_ratio = float(stock.info.get("trailingPE", 0))
            dividend_yield = float(stock.info.get("dividendYield", 0) or 0) * 100
            market_cap = round(float(stock.info.get("marketCap", 0)) / 1e6, 2)
            volume = int(stock_data["Volume"].iloc[-1])

            print(f"📊 {ticker} P/E: {pe_ratio}, Div Yield: {dividend_yield}%, Market Cap: {market_cap}M, Volume: {volume}")

            cur.execute(
                """INSERT INTO Market_Analysis (stock_ticker, pe_ratio, dividend_yield, market_cap, volume)
                   VALUES (%s, %s, %s, %s, %s)
                   ON CONFLICT (stock_ticker) 
                   DO UPDATE SET 
                       pe_ratio = EXCLUDED.pe_ratio,
                       dividend_yield = EXCLUDED.dividend_yield,
                       market_cap = EXCLUDED.market_cap,
                       volume = EXCLUDED.volume;""",
                (ticker, pe_ratio, dividend_yield, market_cap, volume)
            )

            # Fetch and update Yearly Financials Table
            eps_growth = float(stock.info.get("earningsGrowth", 0))
            revenue_growth = float(stock.info.get("revenueGrowth", 0))
            profit = round(float(stock.info.get("netIncomeToCommon", 0)) / 1e6, 2)
            earnings = round(float(stock.info.get("totalRevenue", 0)) / 1e6, 2)
            year = 2024  

            print(f"📈 {ticker} EPS Growth: {eps_growth}, Revenue Growth: {revenue_growth}, Profit: {profit}M, Earnings: {earnings}M")

            cur.execute(
                """INSERT INTO Yearly_Financials (stock_ticker, year, eps_growth, revenue_growth, profit, earnings)
                   VALUES (%s, %s, %s, %s, %s, %s)
                   ON CONFLICT (stock_ticker, year) 
                   DO UPDATE SET 
                       eps_growth = EXCLUDED.eps_growth,
                       revenue_growth = EXCLUDED.revenue_growth,
                       profit = EXCLUDED.profit,
                       earnings = EXCLUDED.earnings;""",
                (ticker, year, eps_growth, revenue_growth, profit, earnings)
            )

        except Exception as e:
            print(f"❌ Error updating {ticker}: {e}")

    conn.commit()  # ✅ Commit all changes at once (Faster)
    cur.close()
    app.config["DB_POOL"].putconn(conn)  # ✅ Return connection to the pool

    print("✅ All stock data updated successfully!")

if __name__ == "__main__":
    update_stock_prices()
