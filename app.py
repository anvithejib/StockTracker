# -------------------------------
# Raw SQL Code: Create Tables
# -------------------------------
CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS Brokers (
    brokerage_id SERIAL PRIMARY KEY,
    name VARCHAR(255) UNIQUE NOT NULL,
    user_count INT DEFAULT 0
);

CREATE TABLE IF NOT EXISTS Users (
    user_id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    password_hash TEXT NOT NULL,
    brokerage_id INT REFERENCES Brokers(brokerage_id),
    balance NUMERIC(15,2) DEFAULT 0
);

CREATE TABLE IF NOT EXISTS Stock (
    ticker VARCHAR(20) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    price NUMERIC(10,2),
    high_52 NUMERIC(10,2),
    low_52 NUMERIC(10,2)
);

CREATE TABLE IF NOT EXISTS Transactions (
    transaction_id SERIAL PRIMARY KEY,
    user_id INT REFERENCES Users(user_id),
    stock_ticker VARCHAR(20) REFERENCES Stock(ticker),
    type VARCHAR(10) CHECK (type IN ('BUY', 'SELL')),
    quantity INT CHECK (quantity > 0),
    price NUMERIC(10,2),
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS Quarterly_Financials (
    stock_ticker VARCHAR(20) REFERENCES Stock(ticker),
    quarter VARCHAR(10) NOT NULL,
    eps_growth NUMERIC(5,2),
    revenue_growth NUMERIC(5,2),
    profit NUMERIC(15,2),
    earnings NUMERIC(15,2),
    PRIMARY KEY (stock_ticker, quarter)
);

CREATE TABLE IF NOT EXISTS Yearly_Financials (
    stock_ticker VARCHAR(20) REFERENCES Stock(ticker),
    year INT NOT NULL,
    eps_growth NUMERIC(5,2),
    revenue_growth NUMERIC(5,2),
    profit NUMERIC(15,2),
    earnings NUMERIC(15,2),
    PRIMARY KEY (stock_ticker, year)
);

CREATE TABLE IF NOT EXISTS Portfolio (
    user_id INT REFERENCES Users(user_id),
    stock_ticker VARCHAR(20) REFERENCES Stock(ticker),
    quantity INT CHECK (quantity >= 0),
    avg_price NUMERIC(10,2),
    PRIMARY KEY (user_id, stock_ticker)
);

CREATE TABLE IF NOT EXISTS Market_Analysis (
    stock_ticker VARCHAR(20) REFERENCES Stock(ticker) PRIMARY KEY,
    pe_ratio NUMERIC(10,2),
    dividend_yield NUMERIC(5,2),
    market_cap NUMERIC(15,2),
    volume BIGINT
);
"""

# -------------------------------
# Raw SQL Code: Create Stored Functions
# -------------------------------
CREATE_FUNCTIONS_SQL = """
CREATE OR REPLACE FUNCTION buy_stock(
    p_user_id INT,
    p_ticker VARCHAR,
    p_quantity INT,
    p_price NUMERIC
) RETURNS VOID AS $$
BEGIN
    INSERT INTO Transactions (user_id, stock_ticker, type, quantity, price, timestamp)
    VALUES (p_user_id, p_ticker, 'BUY', p_quantity, p_price, CURRENT_TIMESTAMP);
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION sell_stock(
    p_user_id INT,
    p_ticker VARCHAR,
    p_quantity INT,
    p_price NUMERIC
) RETURNS VOID AS $$
DECLARE
    existing_shares INT;
    total_earnings NUMERIC;
BEGIN
    SELECT quantity INTO existing_shares FROM Portfolio WHERE user_id = p_user_id AND stock_ticker = p_ticker;
    IF existing_shares IS NULL OR existing_shares < p_quantity THEN
        RAISE EXCEPTION 'Not enough shares to sell';
    END IF;
    total_earnings := p_quantity * p_price;
    IF existing_shares = p_quantity THEN
        DELETE FROM Portfolio WHERE user_id = p_user_id AND stock_ticker = p_ticker;
    ELSE
        UPDATE Portfolio SET quantity = quantity - p_quantity WHERE user_id = p_user_id AND stock_ticker = p_ticker;
    END IF;
    UPDATE Users SET balance = balance + total_earnings WHERE user_id = p_user_id;
    INSERT INTO Transactions (user_id, stock_ticker, type, quantity, price, timestamp)
    VALUES (p_user_id, p_ticker, 'SELL', p_quantity, p_price, CURRENT_TIMESTAMP);
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION get_high_stocks()
RETURNS TABLE (ticker VARCHAR, name VARCHAR, high_52 NUMERIC, low_52 NUMERIC) AS $$
BEGIN
    RETURN QUERY
    SELECT ticker, name, high_52, low_52
    FROM Stock
    WHERE high_52 >= 2.1 * low_52  -- ✅ 52W High is at least 2.1x the Low
    ORDER BY high_52 DESC;         -- ✅ Sort by highest high_52 first
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION get_low_stocks()
RETURNS TABLE (ticker VARCHAR, name VARCHAR, high_52 NUMERIC, low_52 NUMERIC) AS $$
BEGIN
    RETURN QUERY
    SELECT ticker, name, high_52, low_52
    FROM Stock
    WHERE low_52 = low_52  -- ✅ Ensures low_52 is unchanged (1x itself)
    ORDER BY low_52 ASC;   -- ✅ Sort by lowest low_52 first
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION filter_stocks(
    min_eps NUMERIC,
    max_pe NUMERIC
) RETURNS TABLE (ticker VARCHAR, name VARCHAR, eps NUMERIC, pe NUMERIC) AS $$
BEGIN
    RETURN QUERY
    SELECT s.ticker, s.name, yf.eps_growth, ma.pe_ratio
    FROM Stock s
    JOIN Yearly_Financials yf ON s.ticker = yf.stock_ticker
    JOIN Market_Analysis ma ON s.ticker = ma.stock_ticker
    WHERE yf.eps_growth >= min_eps AND ma.pe_ratio <= max_pe;
END;
$$ LANGUAGE plpgsql;


CREATE OR REPLACE FUNCTION get_user_portfolio(user_id_param INT)
RETURNS TABLE (
    stock_ticker VARCHAR(10),
    stock_name VARCHAR(255),
    quantity INT,
    avg_price NUMERIC(10,2),
    current_price NUMERIC(10,2),
    total_investment NUMERIC(15,2),
    current_value NUMERIC(15,2),
    profit_loss NUMERIC(15,2),
    profit_loss_pct NUMERIC(6,2),
    total_portfolio_investment NUMERIC(15,2),
    total_portfolio_value NUMERIC(15,2),
    total_portfolio_pnl NUMERIC(15,2)
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        s.ticker AS stock_ticker,
        s.name AS stock_name,
        p.quantity,
        p.avg_price,
        s.price AS current_price,
        (p.quantity * p.avg_price) AS total_investment,
        (p.quantity * s.price) AS current_value,
        (p.quantity * s.price) - (p.quantity * p.avg_price) AS profit_loss,
        ROUND(
            ((p.quantity * s.price) - (p.quantity * p.avg_price)) / NULLIF((p.quantity * p.avg_price), 0) * 100, 
            2
        ) AS profit_loss_pct,
        (SELECT SUM(p2.quantity * p2.avg_price) 
         FROM Portfolio p2 WHERE p2.user_id = user_id_param) AS total_portfolio_investment,
        (SELECT SUM(p2.quantity * s2.price) 
         FROM Portfolio p2 
         JOIN Stock s2 ON p2.stock_ticker = s2.ticker 
         WHERE p2.user_id = user_id_param) AS total_portfolio_value,
        (SELECT SUM((p2.quantity * s2.price) - (p2.quantity * p2.avg_price)) 
         FROM Portfolio p2 
         JOIN Stock s2 ON p2.stock_ticker = s2.ticker 
         WHERE p2.user_id = user_id_param) AS total_portfolio_pnl
    FROM Portfolio p
    JOIN Stock s ON p.stock_ticker = s.ticker
    WHERE p.user_id = user_id_param;
END;
$$ LANGUAGE plpgsql;



CREATE OR REPLACE FUNCTION get_portfolio_summary(user_id_param INT)
RETURNS TABLE(stock_name TEXT, total_shares INT, total_value NUMERIC) AS $$
BEGIN
    RETURN QUERY 
    SELECT s.name, SUM(t.quantity) AS total_shares, 
           SUM(t.quantity * sp.price) AS total_value
    FROM Transactions t
    JOIN Stock s ON t.stock_id = s.stock_id
    JOIN Stock_Prices sp ON s.stock_id = sp.stock_id
    WHERE t.user_id = user_id_param AND sp.date = CURRENT_DATE
    GROUP BY s.name;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION get_moving_averages(stock_ticker TEXT)
RETURNS TABLE (
    stock_id INT,
    ticker TEXT,
    moving_avg_50 DECIMAL(10,2),
    moving_avg_200 DECIMAL(10,2)
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        s.stock_id, s.ticker,
        (SELECT AVG(price) FROM Stock_Prices WHERE stock_id = s.stock_id AND date >= CURRENT_DATE - INTERVAL '50 days') AS moving_avg_50,
        (SELECT AVG(price) FROM Stock_Prices WHERE stock_id = s.stock_id AND date >= CURRENT_DATE - INTERVAL '200 days') AS moving_avg_200
    FROM Stock s
    WHERE s.ticker = stock_ticker;
END;
$$ LANGUAGE plpgsql;


"""


import psycopg2
from psycopg2 import pool
from flask import Flask,current_app,session
from flask_login import LoginManager,current_user
from auth import auth
from portfolio import portfolio
from transactions import transactions
from stock_details import stock_details
from models import User
from buy_stocks import buy_stocks
from admin_blueprint import admin

# -------------------------------
# Initialize Flask App
# -------------------------------
app = Flask(__name__)
app.config["DATABASE_URL"] = "postgresql://neondb_owner:npg_2VY3IFQqtPlj@ep-bitter-tooth-a5v8si2g-pooler.us-east-2.aws.neon.tech/neondb?sslmode=require"
app.secret_key = "supersecretkey"

# ✅ Initialize PostgreSQL Connection Pool
try:
    app.config["DB_POOL"] = pool.SimpleConnectionPool(
        minconn=1,
        maxconn=10,
        dsn=app.config["DATABASE_URL"]
    )
    print("✅ Database Pool Initialized")
except Exception as e:
    print(f"❌ Database Pool Initialization Failed: {e}")
    exit(1)  # Stop execution if the pool fails

# -------------------------------
# Helper Function for Queries
# -------------------------------
def fetch_data(query, params=None, fetch_one=False):
    """ Fetch data from PostgreSQL using connection pooling """
    conn = app.config["DB_POOL"].getconn()  # ✅ Use the correct pool
    try:
        with conn.cursor() as cur:
            cur.execute(query, params or ())
            result = cur.fetchone() if fetch_one else cur.fetchall()
            return result
    finally:
        app.config["DB_POOL"].putconn(conn)  # ✅ Return connection to pool

def execute_query(query, params=None):
    """ Execute queries that modify data (INSERT, UPDATE, DELETE) """
    conn = app.config["DB_POOL"].getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(query, params or ())
            conn.commit()
    finally:
        app.config["DB_POOL"].putconn(conn)

# -------------------------------
# Flask-Login Configuration
# -------------------------------
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "auth.login"

app.config['ADMIN_USERS'] = {
    'admin1': 'password1',
    'admin2': 'password2'
}

@login_manager.user_loader
def load_user(user_id):
    """Handle both admin and regular users"""
    # Admin user case
    if user_id == "0" and 'admin_name' in session:
        return User(
            user_id=0,
            name=session['admin_name'],
            password_hash="",
            brokerage_id=None,
            balance=0,
            is_admin=True
        )
    
    # Regular user case
    conn = current_app.config["DB_POOL"].getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT user_id, name, password_hash, brokerage_id, balance FROM Users WHERE user_id = %s",
                (user_id,)
            )
            user_data = cur.fetchone()
            if user_data:
                return User(*user_data, is_admin=False)
    except Exception as e:
        print(f"Error loading user: {e}")
    finally:
        current_app.config["DB_POOL"].putconn(conn)
    return None
# -------------------------------
# Initialize Database
# -------------------------------
def initialize_database():
    """ Creates tables and stored functions in PostgreSQL """
    execute_query(CREATE_TABLES_SQL)
    execute_query(CREATE_FUNCTIONS_SQL)
    print("✅ Tables and functions created successfully!")

# -------------------------------
# Register Blueprints
# -------------------------------
app.register_blueprint(auth)
app.register_blueprint(portfolio, url_prefix="/portfolio")
app.register_blueprint(transactions, url_prefix="/transactions")
app.register_blueprint(stock_details, url_prefix="/stock")
app.register_blueprint(buy_stocks, url_prefix="/buy-stocks")
app.register_blueprint(admin, url_prefix="/admin")

# -------------------------------
# Run Flask App
# -------------------------------
if __name__ == "__main__":
    initialize_database()  # ✅ Ensure tables and functions are created before running the app
    app.run(debug=True)
