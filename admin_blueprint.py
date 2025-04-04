from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, session
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash
import psycopg2

admin = Blueprint("admin", __name__)

def fetch_data(query, params=None):
    """Fetch data using Flask connection pool."""
    conn = current_app.config["DB_POOL"].getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(query, params or ())
            column_names = [desc[0] for desc in cur.description]
            return [dict(zip(column_names, row)) for row in cur.fetchall()]
    finally:
        current_app.config["DB_POOL"].putconn(conn)

def execute_query(query, params=None):
    """Execute write operations with proper transaction handling."""
    conn = current_app.config["DB_POOL"].getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(query, params or ())
            conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        current_app.config["DB_POOL"].putconn(conn)

@admin.route('/dashboard')
@login_required
def admin_dashboard():
    if not current_user.is_admin:
        flash("Admin privileges required", "error")
        return redirect(url_for('portfolio.view_portfolio'))
    
    try:
        # Get all users with brokerage info
        users = fetch_data("""
            SELECT u.user_id, u.name, b.name as brokerage_name, u.balance 
            FROM Users u
            JOIN Brokers b ON u.brokerage_id = b.brokerage_id
            ORDER BY u.name
        """)
        
        # Get brokerage user counts
        brokerages = fetch_data("""
            SELECT b.brokerage_id, b.name, COUNT(u.user_id) as user_count
            FROM Brokers b
            LEFT JOIN Users u ON b.brokerage_id = u.brokerage_id
            GROUP BY b.brokerage_id, b.name
            ORDER BY user_count DESC
        """)
        
        # Get all stocks
        stocks = fetch_data("SELECT ticker, name, price FROM Stock ORDER BY ticker")
        
        return render_template('admin_dashboard.html',
                            users_data=users,
                            brokerages_data=brokerages,
                            stocks_data=stocks)
    except Exception as e:
        flash(f"Error loading dashboard: {str(e)}", "error")
        return redirect(url_for('portfolio.view_portfolio'))

@admin.route("/delete_user/<int:user_id>")
@login_required
def delete_user(user_id):
    if not current_user.is_admin:
        flash("Admin privileges required", "error")
        return redirect(url_for("portfolio.view_portfolio"))
    
    try:
        execute_query("DELETE FROM Users WHERE user_id = %s", (user_id,))
        flash("User deleted successfully", "success")
    except Exception as e:
        flash(f"Error deleting user: {str(e)}", "error")
    
    return redirect(url_for("admin.admin_dashboard"))

@admin.route("/reset_password/<int:user_id>", methods=["POST"])
@login_required
def reset_password(user_id):
    if not current_user.is_admin:
        flash("Admin privileges required", "error")
        return redirect(url_for("portfolio.view_portfolio"))
    
    new_password = request.form.get("new_password")
    if not new_password or len(new_password) < 8:
        flash("Password must be at least 8 characters", "error")
        return redirect(url_for("admin.admin_dashboard"))
    
    try:
        hashed_password = generate_password_hash(new_password)
        execute_query(
            "UPDATE Users SET password_hash = %s WHERE user_id = %s",
            (hashed_password, user_id)
        )
        flash("Password reset successfully", "success")
    except Exception as e:
        flash(f"Error resetting password: {str(e)}", "error")
    
    return redirect(url_for("admin.admin_dashboard"))

@admin.route("/add_stock", methods=["POST"])
@login_required
def add_stock():
    if not current_user.is_admin:
        flash("Admin privileges required", "error")
        return redirect(url_for("portfolio.view_portfolio"))
    
    ticker = request.form.get("ticker", "").upper()
    name = request.form.get("stock_name", "")
    price = request.form.get("stock_price", 0)
    
    if not ticker or not name:
        flash("Ticker and name are required", "error")
        return redirect(url_for("admin.admin_dashboard"))
    
    try:
        execute_query(
            """INSERT INTO Stock (ticker, name, price) 
            VALUES (%s, %s, %s)
            ON CONFLICT (ticker) DO UPDATE
            SET name = EXCLUDED.name,
                price = EXCLUDED.price""",
            (ticker, name, float(price))
        )
        flash(f"Stock {ticker} added/updated successfully", "success")
    except psycopg2.IntegrityError:
        flash(f"Stock {ticker} already exists", "error")
    except Exception as e:
        flash(f"Error adding stock: {str(e)}", "error")
    
    return redirect(url_for("admin.admin_dashboard"))

@admin.route("/delete_stock/<ticker>", methods=["POST"])
@login_required
def delete_stock(ticker):
    if not current_user.is_admin:
        flash("Admin privileges required", "error")
        return redirect(url_for("portfolio.view_portfolio"))
    
    try:
        # First delete from Portfolio (watchlists) to avoid FK constraint errors
        execute_query("DELETE FROM Portfolio WHERE stock_ticker = %s", (ticker,))
        # Then delete the stock
        execute_query("DELETE FROM Stock WHERE ticker = %s", (ticker,))
        flash(f"Stock {ticker} deleted successfully", "success")
    except Exception as e:
        flash(f"Error deleting stock: {str(e)}", "error")
    
    return redirect(url_for("admin.admin_dashboard"))

@admin.route('/check_session')
def check_session():
    """Debug endpoint to check session status"""
    return f"""
    Logged in: {current_user.is_authenticated}<br>
    User ID: {getattr(current_user, 'user_id', None)}<br>
    Admin: {getattr(current_user, 'is_admin', None)}<br>
    Session: {dict(session)}
    """