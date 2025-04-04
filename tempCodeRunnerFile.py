        WITH TransactionHistory AS (
                SELECT
                    t.transaction_id,
                    t.timestamp::DATE AS date,
                    t.stock_ticker,
                    t.type,
                    t.quantity,
                    t.price,
                    (t.quantity * t.price) AS transaction_amount
                FROM Transactions t
                WHERE t.user_id = %s
            ),
            RealizedPnl AS (
                SELECT 
                    t.stock_ticker,
                    SUM(
                        CASE 
                            WHEN t.type = 'SELL' THEN (t.quantity * (t.price - p.avg_price))
                            ELSE 0 
                        END
                    ) AS realized_pnl
                FROM Transactions t
                JOIN Portfolio p ON t.stock_ticker = p.stock_ticker AND t.user_id = p.user_id
                WHERE t.user_id = %s
                GROUP BY t.stock_ticker
            ),
            UnrealizedPnl AS (
                SELECT 
                    p.stock_ticker,
                    (p.quantity * (s.price - p.avg_price)) AS unrealized_pnl
                FROM Portfolio p
                JOIN Stock s ON p.stock_ticker = s.ticker
                WHERE p.user_id = %s
            )
            SELECT th.*, rp.realized_pnl, up.unrealized_pnl
            FROM TransactionHistory th
            LEFT JOIN RealizedPnl rp ON th.stock_ticker = rp.stock_ticker
            LEFT JOIN UnrealizedPnl up ON th.stock_ticker = up.stock_ticker;
