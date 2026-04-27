"""
Portfolio service layer providing database operations for user stock positions.

Notes
-----
This module handles CRUD operations, price averaging logic, and P&L calculations.
All SQL queries use parameterized statements to prevent injection.
"""
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Optional
from uuid import UUID, uuid4
from decimal import Decimal
import math
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

import sys
sys.path.insert(0, '/app')

from app.schema.schemas import (
    PortfolioItem,
    PortfolioCreateItem,
    PortfolioUpdateItem,
    PortfolioItemWithMetrics,
    PortfolioSummary,
    PortfolioSummaryResponse
)


def safe_float(value, default=0.0):
    """
    Safely convert a value to float, returning a default for None, NaN, or infinity.

    Notes
    -----
    Returns None when value is None and default is 0.0, preserving optional fields.
    """
    if value is None:
        return None if default == 0.0 else default
    try:
        f = float(value)
        if math.isnan(f) or math.isinf(f):
            return default
        return f
    except (ValueError, TypeError) as e:
        return default
    
def row_to_dict(row):
    """Convert SQLAlchemy Row or dict to dict"""
    if row is None:
        return None
    if hasattr(row, '_mapping'):
        return dict(row._mapping)
    return row

def safe_datetime_to_str(value):
    """Convert datetime to ISO string, or keep string as is"""
    if value is None:
        return None
    if isinstance(value, str):
        return value  
    if hasattr(value, 'isoformat'):
        return value.isoformat()  # Convert datetime to string
    return str(value)  # Fallback


def get_user_portfolio(db: Session, user_id: UUID) -> List[PortfolioItem]:
    """Get all portfolio items for a user"""
    sql = text("""
        SELECT 
            id, user_id, ticker, quantity, avg_price, added_at
        FROM portfolio
        WHERE user_id = :user_id
        ORDER BY added_at DESC
    """)
    
    rows = db.execute(sql, {"user_id": str(user_id)}).fetchall()
    
    result = []
    for row in rows:
        row_dict = row_to_dict(row)
        result.append(PortfolioItem(
            id=row_dict["id"],
            user_id=row_dict["user_id"],
            ticker=row_dict["ticker"],
            quantity=float(row_dict["quantity"]),
            avg_price=float(row_dict["avg_price"]),
            added_at=safe_datetime_to_str(row_dict["added_at"])
        ))
    return result


def get_portfolio_item_by_ticker(
    db: Session, user_id: UUID, ticker: str
) -> Optional[PortfolioItem]:
    """Get a specific portfolio item by ticker"""
    sql = text("""
        SELECT id, user_id, ticker, quantity, avg_price, added_at
        FROM portfolio
        WHERE user_id = :user_id AND ticker = :ticker
    """)
    
    row = db.execute(sql, {"user_id": str(user_id), "ticker": ticker}).fetchone()
    if not row:
        return None
    
    row_dict = row_to_dict(row)
    return PortfolioItem(
        id=row_dict["id"],
        user_id=row_dict["user_id"],
        ticker=row_dict["ticker"],
        quantity=float(row_dict["quantity"]),
        avg_price=float(row_dict["avg_price"]),
        added_at=safe_datetime_to_str(row_dict["added_at"])
    )


def add_or_update_position(
    db: Session, user_id: UUID, item: PortfolioCreateItem
) -> PortfolioItem:
    logger.info(f"add_or_update_position called: user={user_id}, ticker={item.ticker}, qty={item.quantity}, price={item.avg_price}")
    
    try:
        existing = db.execute(
            text("""
                SELECT id, quantity, avg_price
                FROM portfolio
                WHERE user_id = :user_id AND ticker = :ticker
            """),
            {"user_id": str(user_id), "ticker": item.ticker},
        ).fetchone()

        logger.info(f"Existing position found: {existing is not None}")

        if existing:
            d = row_to_dict(existing)
            old_qty   = float(d["quantity"])
            old_price = float(d["avg_price"])
            new_qty   = old_qty + item.quantity
            new_price = (old_qty * old_price + item.quantity * item.avg_price) / new_qty
            logger.info(f"Updating position: new_qty={new_qty}, new_price={new_price}")

            db.execute(
                text("UPDATE portfolio SET quantity = :qty, avg_price = :price WHERE id = :id"),
                {"id": d["id"], "qty": new_qty, "price": new_price},
            )
        else:
            new_id = str(uuid4())
            logger.info(f"Inserting new position: id={new_id}")
            db.execute(
                text("""
                    INSERT INTO portfolio (id, user_id, ticker, quantity, avg_price)
                    VALUES (:id, :user_id, :ticker, :quantity, :avg_price)
                """),
                {
                    "id":        new_id,
                    "user_id":   str(user_id),
                    "ticker":    item.ticker,
                    "quantity":  item.quantity,
                    "avg_price": item.avg_price,
                },
            )

        _log_transaction(db, user_id, item.ticker, "buy", item.quantity, item.avg_price, executed_at=getattr(item, 'purchase_date', None))
        db.commit()
        logger.info(f"Committed successfully for {item.ticker}")

        result = get_portfolio_item_by_ticker(db, user_id, item.ticker)
        logger.info(f"Fetched back result: {result}")
        return result

    except Exception as e:
        logger.error(f"Error in add_or_update_position: {e}", exc_info=True)
        db.rollback()
        raise
    
def _log_transaction(db: Session, user_id: UUID, ticker: str, action: str, quantity: float, price: float, realized_gain: Optional[float] = None, executed_at: Optional[str] = None) -> str:
    row = db.execute(text("""
        INSERT INTO transactions (user_id, ticker, action, quantity, price, realized_gain, executed_at)
        VALUES (:uid, :ticker, :action, :qty, :price, :gain, COALESCE(CAST(:executed_at AS timestamptz), now()))
        RETURNING id
    """), {
        "uid": str(user_id),
        "ticker": ticker,
        "action": action,
        "qty": quantity,
        "price": price,
        "gain": realized_gain,
        "executed_at": executed_at,
        },
    ).fetchone()
    transaction_id = str(row_to_dict(row)["id"]) if row else ""
    logger.info(
        "Logged transaction: id=%s user=%s ticker=%s action=%s qty=%s price=%s",
        transaction_id,
        user_id,
        ticker,
        action,
        quantity,
        price,
    )
    return transaction_id

def update_portfolio_item(
    db: Session, user_id: UUID, ticker: str, item: PortfolioUpdateItem
) -> Optional[PortfolioItem]:
    existing = get_portfolio_item_by_ticker(db, user_id, ticker)
    if not existing:
        return None
    
    update_fields = []
    params = {"user_id": str(user_id), "ticker": ticker}
    
    if item.quantity is not None:
        update_fields.append("quantity = :quantity")
        params["quantity"] = item.quantity
    
    if item.avg_price is not None:
        update_fields.append("avg_price = :avg_price")
        params["avg_price"] = item.avg_price
    
    if not update_fields:
        return None
    
    sql = text(f"""
        UPDATE portfolio
        SET {', '.join(update_fields)}
        WHERE user_id = :user_id AND ticker = :ticker
    """)
    
    result = db.execute(sql, params)

    if item.quantity is not None and item.quantity < existing.quantity:
        qty_sold = existing.quantity - item.quantity
        sell_price = _get_latest_price(db, ticker) or existing.avg_price
        realized_gain = (sell_price - existing.avg_price) * qty_sold
        _log_transaction(db, user_id, ticker, "sell", qty_sold, sell_price, realized_gain)
    db.commit()
    if result.rowcount == 0:
        return None
    return get_portfolio_item_by_ticker(db, user_id, ticker)

def _get_latest_price(db: Session, ticker: str) -> Optional[float]:
    row = db.execute(text("""
        SELECT close FROM stocks
        WHERE ticker = :ticker
        ORDER BY date DESC LIMIT 1
    """), {"ticker": ticker}).fetchone()
    return float(row[0]) if row and row[0] is not None else None

def remove_from_portfolio(db: Session, user_id: UUID, ticker: str) -> bool:
    existing = get_portfolio_item_by_ticker(db, user_id, ticker)
    if existing:
        sell_price = _get_latest_price(db, ticker) or existing.avg_price
        realized_gain = (sell_price - existing.avg_price) * existing.quantity \
                        if sell_price else None
        _log_transaction(db, user_id, ticker, "sell", existing.quantity, sell_price, realized_gain)

    sql = text("""
        DELETE FROM portfolio
        WHERE user_id = :user_id AND ticker = :ticker
    """)
    
    result = db.execute(sql, {"user_id": str(user_id), "ticker": ticker})
    db.commit()
    return result.rowcount > 0


def delete_transaction(db: Session, user_id: UUID, transaction_id: str) -> bool:
    """
    Delete a single transaction and adjust the portfolio position for that ticker.

    Strategy differs by action:
    - sell: add the sold quantity back to the current position (or recreate the
      position if it was fully closed). avg_price is unchanged for sells.
    - buy: subtract the bought quantity and recompute avg_price from the
      remaining buy transactions. Removes the portfolio row if nothing is left.

    Returns False if the transaction does not belong to this user.
    """
    tx_row = db.execute(
        text("""
            SELECT id, ticker, action, quantity, price
            FROM transactions
            WHERE id = :tid AND user_id = :uid
        """),
        {"tid": transaction_id, "uid": str(user_id)},
    ).fetchone()

    if not tx_row:
        existing_any_user = db.execute(
            text("""
                SELECT user_id, ticker, action, quantity, price
                FROM transactions
                WHERE id = :tid
            """),
            {"tid": transaction_id},
        ).fetchone()
        if existing_any_user:
            existing = row_to_dict(existing_any_user)
            logger.warning(
                "Delete transaction denied: id=%s requested_user=%s owner_user=%s ticker=%s action=%s qty=%s price=%s",
                transaction_id,
                user_id,
                existing["user_id"],
                existing["ticker"],
                existing["action"],
                existing["quantity"],
                existing["price"],
            )
        else:
            logger.warning(
                "Delete transaction failed: id=%s requested_user=%s not found",
                transaction_id,
                user_id,
            )
        return False

    tx = row_to_dict(tx_row)
    ticker = tx["ticker"]
    action = tx["action"]
    tx_qty = float(tx["quantity"])
    tx_price = float(tx["price"])

    db.execute(
        text("DELETE FROM transactions WHERE id = :tid AND user_id = :uid"),
        {"tid": transaction_id, "uid": str(user_id)},
    )

    existing = db.execute(
        text("SELECT id, quantity, avg_price FROM portfolio WHERE user_id = :uid AND ticker = :ticker"),
        {"uid": str(user_id), "ticker": ticker},
    ).fetchone()
    existing_d = row_to_dict(existing) if existing else None

    if action == "sell":
        # Deleting a sell: give the shares back. avg_price is unaffected by sells.
        if existing_d:
            new_qty = float(existing_d["quantity"]) + tx_qty
            db.execute(
                text("UPDATE portfolio SET quantity = :qty WHERE user_id = :uid AND ticker = :ticker"),
                {"qty": new_qty, "uid": str(user_id), "ticker": ticker},
            )
        else:
            # Position was fully closed by this sell. Recreate it.
            # Use avg_price from remaining buy transactions when available,
            # falling back to the sell price (best approximation with no buy log).
            agg = db.execute(
                text("""
                    SELECT
                        SUM(CASE WHEN action = 'buy' THEN quantity * price ELSE 0 END)
                            / NULLIF(SUM(CASE WHEN action = 'buy' THEN quantity ELSE 0 END), 0)
                        AS avg_buy_price
                    FROM transactions
                    WHERE user_id = :uid AND ticker = :ticker
                """),
                {"uid": str(user_id), "ticker": ticker},
            ).fetchone()
            avg_price = float((row_to_dict(agg) or {}).get("avg_buy_price") or tx_price)
            db.execute(
                text("INSERT INTO portfolio (id, user_id, ticker, quantity, avg_price) VALUES (:id, :uid, :ticker, :qty, :price)"),
                {"id": str(uuid4()), "uid": str(user_id), "ticker": ticker, "qty": tx_qty, "price": avg_price},
            )

    else:  # action == "buy"
        # Deleting a buy: recompute position entirely from remaining transactions.
        agg = db.execute(
            text("""
                SELECT
                    SUM(CASE WHEN action = 'buy' THEN quantity ELSE -quantity END) AS net_qty,
                    SUM(CASE WHEN action = 'buy' THEN quantity * price ELSE 0 END)
                        / NULLIF(SUM(CASE WHEN action = 'buy' THEN quantity ELSE 0 END), 0)
                        AS avg_buy_price
                FROM transactions
                WHERE user_id = :uid AND ticker = :ticker
            """),
            {"uid": str(user_id), "ticker": ticker},
        ).fetchone()
        agg_d = row_to_dict(agg)
        net_qty = float(agg_d["net_qty"] or 0)
        avg_buy_price = float(agg_d["avg_buy_price"] or 0)

        if net_qty <= 0 or avg_buy_price <= 0:
            db.execute(
                text("DELETE FROM portfolio WHERE user_id = :uid AND ticker = :ticker"),
                {"uid": str(user_id), "ticker": ticker},
            )
        elif existing_d:
            db.execute(
                text("UPDATE portfolio SET quantity = :qty, avg_price = :price WHERE user_id = :uid AND ticker = :ticker"),
                {"qty": net_qty, "price": avg_buy_price, "uid": str(user_id), "ticker": ticker},
            )
        else:
            db.execute(
                text("INSERT INTO portfolio (id, user_id, ticker, quantity, avg_price) VALUES (:id, :uid, :ticker, :qty, :price)"),
                {"id": str(uuid4()), "uid": str(user_id), "ticker": ticker, "qty": net_qty, "price": avg_buy_price},
            )

    db.commit()
    return True


def get_portfolio_summary(
    db: Session, user_id: UUID
) -> PortfolioSummaryResponse:
    """Get portfolio summary with current prices and P&L calculations"""
    
    sql = text("""
        WITH latest AS (
            SELECT ticker, MAX(date) AS max_date FROM stocks GROUP BY ticker
        ),
        latest_prices AS (
            SELECT
                s.ticker,
                s.close AS current_price,
                s.date  AS price_date,
                (SELECT s2.close FROM stocks s2
                 WHERE s2.ticker = s.ticker
                   AND s2.date <= s.date - INTERVAL '1 day'
                 ORDER BY s2.date DESC LIMIT 1) AS close_1d_ago,
                (SELECT s2.close FROM stocks s2
                 WHERE s2.ticker = s.ticker
                   AND s2.date <= s.date - INTERVAL '30 days'
                 ORDER BY s2.date DESC LIMIT 1) AS close_30d_ago,
                (SELECT s2.close FROM stocks s2
                 WHERE s2.ticker = s.ticker
                   AND s2.date <= s.date - INTERVAL '120 days'
                 ORDER BY s2.date DESC LIMIT 1) AS close_120d_ago,
                (SELECT s2.close FROM stocks s2
                 WHERE s2.ticker = s.ticker
                   AND s2.date <= s.date - INTERVAL '360 days'
                 ORDER BY s2.date DESC LIMIT 1) AS close_360d_ago
            FROM stocks s
            INNER JOIN latest ON s.ticker = latest.ticker AND s.date = latest.max_date
        )
        SELECT
            p.id,
            p.ticker,
            p.quantity,
            p.avg_price,
            p.added_at,
            lp.current_price,
            lp.price_date,
            CASE WHEN lp.close_1d_ago   IS NOT NULL AND lp.close_1d_ago   <> 0
                 THEN (lp.current_price - lp.close_1d_ago)   / lp.close_1d_ago
                 END AS return_1d,
            CASE WHEN lp.close_30d_ago  IS NOT NULL AND lp.close_30d_ago  <> 0
                 THEN (lp.current_price - lp.close_30d_ago)  / lp.close_30d_ago
                 END AS return_30d,
            CASE WHEN lp.close_120d_ago IS NOT NULL AND lp.close_120d_ago <> 0
                 THEN (lp.current_price - lp.close_120d_ago) / lp.close_120d_ago
                 END AS return_120d,
            CASE WHEN lp.close_360d_ago IS NOT NULL AND lp.close_360d_ago <> 0
                 THEN (lp.current_price - lp.close_360d_ago) / lp.close_360d_ago
                 END AS return_360d,
            (p.quantity * p.avg_price) AS cost_basis,
            (p.quantity * COALESCE(lp.current_price, p.avg_price)) AS current_value,
            (p.quantity * COALESCE(lp.current_price, p.avg_price)) - (p.quantity * p.avg_price) AS total_gain_loss,
            ((COALESCE(lp.current_price, p.avg_price) - p.avg_price) / p.avg_price) AS gain_loss_pct
        FROM portfolio p
        LEFT JOIN latest_prices lp ON p.ticker = lp.ticker
        WHERE p.user_id = :user_id
        ORDER BY p.added_at DESC
    """)
    
    rows = db.execute(sql, {"user_id": str(user_id)}).fetchall()

    realized_row = db.execute(
        text("""
            SELECT
                COALESCE(SUM(realized_gain), 0) AS total_realized_gain
            FROM transactions
            WHERE user_id = :user_id AND action = 'sell' AND realized_gain IS NOT NULL
        """), {"user_id": str(user_id)}
    ).fetchone()

    realized_dict = row_to_dict(realized_row)
    total_realized_gain = float(realized_dict["total_realized_gain"]) if realized_dict and realized_dict["total_realized_gain"] is not None else 0.0

    portfolio_items = []
    total_cost_basis = 0.0
    total_current_value = 0.0
    
    for row in rows:
        row_dict = row_to_dict(row)

        # Log raw values from database
        logger.info(
            f"Processing {row_dict['ticker']}: qty={row_dict['quantity']}, avg_price={row_dict['avg_price']}, "
                   f"current_price={row_dict['current_price']}, cost_basis={row_dict['cost_basis']}, "
                   f"current_value={row_dict['current_value']}, gain_loss={row_dict['total_gain_loss']}, "
                   f"gain_loss_pct={row_dict['gain_loss_pct']}"
        )
        
        # Use safe_float for all conversions
        cost_basis = safe_float(row_dict["cost_basis"], 0.0)
        current_value = safe_float(row_dict["current_value"], 0.0)

        total_cost_basis += cost_basis
        total_current_value += current_value
        
        portfolio_items.append(
            PortfolioItemWithMetrics(
                id=str(row_dict["id"]),
                ticker=row_dict["ticker"],
                quantity=safe_float(row_dict["quantity"], 0.0),
                avg_price=safe_float(row_dict["avg_price"], 0.0),
                current_price=safe_float(row_dict["current_price"]),
                cost_basis=cost_basis,
                current_value=current_value,
                total_gain_loss=safe_float(row_dict["total_gain_loss"], 0.0),
                gain_loss_pct=safe_float(row_dict["gain_loss_pct"], 0.0),
                return_1d=safe_float(row_dict["return_1d"]),
                return_30d=safe_float(row_dict["return_30d"]),
                return_120d=safe_float(row_dict["return_120d"]),
                return_360d=safe_float(row_dict["return_360d"]),
                added_at=safe_datetime_to_str(row_dict["added_at"])
            )
        )

    # Safe final calculations
    total_unrealized_gain = safe_float(total_current_value - total_cost_basis, 0.0)
    total_unrealized_gain_pct = safe_float((total_unrealized_gain / total_cost_basis) if total_cost_basis > 0 else 0.0, 0.0)
    
    summary = PortfolioSummary(
        total_cost_basis=total_cost_basis,
        total_current_value=total_current_value,
        total_gain_loss=total_unrealized_gain,
        total_gain_loss_pct=total_unrealized_gain_pct,
        total_realized_gain=total_realized_gain,
        num_positions=len(portfolio_items)
    )
    
    return PortfolioSummaryResponse(
        portfolio_items=portfolio_items,
        summary=summary
    )

def get_transactions(db: Session, user_id: UUID) -> List[dict]:
    rows = db.execute(text("""
        SELECT id, ticker, action, quantity, price, realized_gain, executed_at
        FROM transactions
        WHERE user_id = :uid
        ORDER BY executed_at DESC
    """), {"uid": str(user_id)}).fetchall()
    return [
        {
            "id":            str(d["id"]),
            "ticker":        d["ticker"],
            "action":        d["action"],
            "quantity":      float(d["quantity"]),
            "price":         float(d["price"]),
            "realized_gain": safe_float(d["realized_gain"]),
            "executed_at":   safe_datetime_to_str(d["executed_at"]),
        }
        for d in (row_to_dict(r) for r in rows)
    ]

def get_realized_summary(db: Session, user_id: UUID) -> List[dict]:
    row = db.execute(
        text("""
            SELECT 
                ticker,
                COALESCE(SUM(realized_gain), 0) AS total_realized,
                COUNT(*) AS num_sells
            FROM transactions
            WHERE user_id = :uid AND action = 'sell'
            GROUP BY ticker
            ORDER BY total_realized DESC
        """), {"uid": str(user_id)}).mappings().all()
    return  [
        {
            "ticker":        r["ticker"],
            "total_realized": float(r["total_realized"]),
            "num_sells":      int(r["num_sells"]),
        }
        for r in row
    ]
