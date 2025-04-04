from flask import Blueprint, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user

transactions = Blueprint("transactions", __name__)

def fetch_data(query, params=()):
    """Fetch data using Flask connection pool."""
    conn = current_app.config["DB_POOL"].getconn()
    cur = conn.cursor()
    cur.execute(query, params)
    result = cur.fetchall()  # Always returns a list of tuples
    cur.close()
    current_app.config["DB_POOL"].putconn(conn)
    return result

def execute_query(query, params=()):
    """Executes a query using Flask connection pool."""
    conn = current_app.config["DB_POOL"].getconn()
    cur = conn.cursor()
    cur.execute(query, params)
    conn.commit()
    cur.close()
    current_app.config["DB_POOL"].putconn(conn)

@transactions.route("/buy", methods=["POST"])
@login_required
def buy_stock():
    ticker = request.form["ticker"].upper()
    quantity = int(request.form["quantity"])

    # ✅ Fetch stock price
    stock_data = fetch_data("SELECT price FROM Stock WHERE ticker = %s;", (ticker,))
    if not stock_data:  # Empty result check
        flash("Stock not found")
        return redirect(url_for("portfolio.view_portfolio"))

    stock_price = stock_data[0][0]  # Safe access
    total_cost = quantity * stock_price

    # ✅ Fetch user balance
    user_balance_data = fetch_data("SELECT balance FROM Users WHERE user_id = %s;", (current_user.user_id,))
    if not user_balance_data or user_balance_data[0][0] < total_cost:
        flash("Insufficient balance")
        return redirect(url_for("portfolio.view_portfolio"))

    # ✅ Deduct balance
    execute_query("UPDATE Users SET balance = balance - %s WHERE user_id = %s;", (total_cost, current_user.user_id))

    # ✅ Insert Transaction
    execute_query(
        "INSERT INTO Transactions (user_id, stock_ticker, type, quantity, price) VALUES (%s, %s, 'BUY', %s, %s);",
        (current_user.user_id, ticker, quantity, stock_price)
    )

    # ✅ Update Portfolio table:
    existing_portfolio = fetch_data(
        "SELECT quantity, avg_price FROM Portfolio WHERE user_id = %s AND stock_ticker = %s;",
        (current_user.user_id, ticker)
    )

    if existing_portfolio:
        old_qty = existing_portfolio[0][0]
        old_avg = existing_portfolio[0][1]
        new_qty = old_qty + quantity
        # Calculate the weighted average price
        new_avg = ((old_qty * old_avg) + (quantity * stock_price)) / new_qty
        execute_query(
            "UPDATE Portfolio SET quantity = %s, avg_price = %s WHERE user_id = %s AND stock_ticker = %s;",
            (new_qty, new_avg, current_user.user_id, ticker)
        )
    else:
        execute_query(
            "INSERT INTO Portfolio (user_id, stock_ticker, quantity, avg_price) VALUES (%s, %s, %s, %s);",
            (current_user.user_id, ticker, quantity, stock_price)
        )

    flash(f"Successfully bought {quantity} shares of {ticker}")
    return redirect(url_for("portfolio.view_portfolio"))

# ✅ Sell Stock
@transactions.route("/sell", methods=["POST"])
@login_required
def sell_stock():
    """Handles selling of stocks"""
    ticker = request.form["ticker"].upper()
    quantity = int(request.form["quantity"])

    # ✅ Fetch stock price
    stock_data = fetch_data("SELECT price FROM Stock WHERE ticker = %s;", (ticker,))
    if not stock_data:
        flash("Stock not found")
        return redirect(url_for("portfolio.view_portfolio"))

    stock_price = stock_data[0][0]
    total_earnings = quantity * stock_price

    # ✅ Check if user owns enough shares
    portfolio_entry = fetch_data(
        "SELECT quantity FROM Portfolio WHERE user_id = %s AND stock_ticker = %s;", 
        (current_user.user_id, ticker)
    )

    if not portfolio_entry or portfolio_entry[0][0] < quantity:
        flash("Not enough shares to sell")
        return redirect(url_for("portfolio.view_portfolio"))

    # ✅ Update Portfolio
    if portfolio_entry[0][0] == quantity:
        execute_query("DELETE FROM Portfolio WHERE user_id = %s AND stock_ticker = %s;", (current_user.user_id, ticker))
    else:
        execute_query(
            "UPDATE Portfolio SET quantity = quantity - %s WHERE user_id = %s AND stock_ticker = %s;",
            (quantity, current_user.user_id, ticker)
        )

    # ✅ Update User Balance
    execute_query("UPDATE Users SET balance = balance + %s WHERE user_id = %s;", (total_earnings, current_user.user_id))

    # ✅ Insert Transaction
    execute_query(
        "INSERT INTO Transactions (user_id, stock_ticker, type, quantity, price) VALUES (%s, %s, 'SELL', %s, %s);",
        (current_user.user_id, ticker, quantity, stock_price)
    )

    flash(f"Successfully sold {quantity} shares of {ticker}")
    return redirect(url_for("portfolio.view_portfolio"))