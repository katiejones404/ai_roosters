from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Optional
from uuid import UUID, uuid4
from datetime import date, timedelta
import math
import logging
import sys

sys.path.insert(0, '/app')

from app.schema.schemas import (
    NetworthAssetCreate,
    NetworthAssetUpdate,
    NetworthAssetOut,
    NetworthLiabilityCreate,
    NetworthLiabilityUpdate,
    NetworthLiabilityOut,
    NetworthSummary,
    NetworthSnapshotOut,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Shared helpers (mirrors portfolio.py)
# ---------------------------------------------------------------------------

def safe_float(value, default=0.0):
    if value is None:
        return None if default == 0.0 else default
    try:
        f = float(value)
        if math.isnan(f) or math.isinf(f):
            return default
        return f
    except (ValueError, TypeError):
        return default


def row_to_dict(row):
    if row is None:
        return None
    if hasattr(row, '_mapping'):
        return dict(row._mapping)
    return row


def safe_datetime_to_str(value):
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if hasattr(value, 'isoformat'):
        return value.isoformat()
    return str(value)


# ---------------------------------------------------------------------------
# Internal: portfolio value from latest stock prices
# ---------------------------------------------------------------------------

def _get_portfolio_value(db: Session, user_id: UUID) -> float:
    sql = text("""
        SELECT COALESCE(SUM(p.quantity * COALESCE(cp.close, p.avg_price)), 0) AS portfolio_value
        FROM portfolio p
        LEFT JOIN (
            SELECT s.ticker, s.close
            FROM stocks s
            INNER JOIN (
                SELECT ticker, MAX(date) AS max_date FROM stocks GROUP BY ticker
            ) latest ON s.ticker = latest.ticker AND s.date = latest.max_date
        ) cp ON p.ticker = cp.ticker
        WHERE p.user_id = :user_id
    """)
    row = db.execute(sql, {"user_id": str(user_id)}).fetchone()
    if row:
        d = row_to_dict(row)
        return safe_float(d["portfolio_value"], 0.0) or 0.0
    return 0.0


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

def get_summary(db: Session, user_id: UUID) -> NetworthSummary:
    portfolio_value = _get_portfolio_value(db, user_id)

    asset_rows = db.execute(
        text("SELECT id, name, category, balance, updated_at FROM networth_assets WHERE user_id = :uid ORDER BY created_at ASC"),
        {"uid": str(user_id)},
    ).fetchall()

    assets: List[NetworthAssetOut] = []
    total_manual_assets = 0.0
    for row in asset_rows:
        d = row_to_dict(row)
        bal = safe_float(d["balance"], 0.0) or 0.0
        total_manual_assets += bal
        assets.append(NetworthAssetOut(
            id=str(d["id"]),
            name=d["name"],
            category=d["category"],
            balance=bal,
            updated_at=safe_datetime_to_str(d["updated_at"]),
        ))

    liab_rows = db.execute(
        text("SELECT id, name, category, balance, updated_at FROM networth_liabilities WHERE user_id = :uid ORDER BY created_at ASC"),
        {"uid": str(user_id)},
    ).fetchall()

    liabilities: List[NetworthLiabilityOut] = []
    total_liabilities = 0.0
    for row in liab_rows:
        d = row_to_dict(row)
        bal = safe_float(d["balance"], 0.0) or 0.0
        total_liabilities += bal
        liabilities.append(NetworthLiabilityOut(
            id=str(d["id"]),
            name=d["name"],
            category=d["category"],
            balance=bal,
            updated_at=safe_datetime_to_str(d["updated_at"]),
        ))

    total_assets = portfolio_value + total_manual_assets
    net_worth = total_assets - total_liabilities

    return NetworthSummary(
        portfolio_value=portfolio_value,
        total_assets=total_assets,
        total_liabilities=total_liabilities,
        net_worth=net_worth,
        assets=assets,
        liabilities=liabilities,
    )


# ---------------------------------------------------------------------------
# History snapshots
# ---------------------------------------------------------------------------

def get_history(db: Session, user_id: UUID, days: int = 30) -> List[NetworthSnapshotOut]:
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    rows = db.execute(
        text("""
            SELECT snapshot_date, net_worth, portfolio_value, total_assets, total_liabilities
            FROM networth_snapshots
            WHERE user_id = :uid AND snapshot_date >= :cutoff
            ORDER BY snapshot_date ASC
        """),
        {"uid": str(user_id), "cutoff": cutoff},
    ).fetchall()

    result = []
    for row in rows:
        d = row_to_dict(row)
        result.append(NetworthSnapshotOut(
            snapshot_date=str(d["snapshot_date"]),
            net_worth=safe_float(d["net_worth"], 0.0) or 0.0,
            portfolio_value=safe_float(d["portfolio_value"], 0.0) or 0.0,
            total_assets=safe_float(d["total_assets"], 0.0) or 0.0,
            total_liabilities=safe_float(d["total_liabilities"], 0.0) or 0.0,
        ))
    return result


def record_snapshot(db: Session, user_id: UUID) -> None:
    summary = get_summary(db, user_id)
    today = date.today().isoformat()
    db.execute(
        text("""
            INSERT INTO networth_snapshots
                (id, user_id, snapshot_date, portfolio_value, total_assets, total_liabilities, net_worth)
            VALUES (:id, :uid, :snapshot_date, :pv, :ta, :tl, :nw)
            ON CONFLICT (user_id, snapshot_date)
            DO UPDATE SET
                portfolio_value   = EXCLUDED.portfolio_value,
                total_assets      = EXCLUDED.total_assets,
                total_liabilities = EXCLUDED.total_liabilities,
                net_worth         = EXCLUDED.net_worth
        """),
        {
            "id": str(uuid4()),
            "uid": str(user_id),
            "snapshot_date": today,
            "pv": summary.portfolio_value,
            "ta": summary.total_assets,
            "tl": summary.total_liabilities,
            "nw": summary.net_worth,
        },
    )
    db.commit()


# ---------------------------------------------------------------------------
# Asset CRUD
# ---------------------------------------------------------------------------

def get_assets(db: Session, user_id: UUID) -> List[NetworthAssetOut]:
    rows = db.execute(
        text("SELECT id, name, category, balance, updated_at FROM networth_assets WHERE user_id = :uid ORDER BY created_at ASC"),
        {"uid": str(user_id)},
    ).fetchall()
    result = []
    for row in rows:
        d = row_to_dict(row)
        result.append(NetworthAssetOut(
            id=str(d["id"]),
            name=d["name"],
            category=d["category"],
            balance=safe_float(d["balance"], 0.0) or 0.0,
            updated_at=safe_datetime_to_str(d["updated_at"]),
        ))
    return result


def add_asset(db: Session, user_id: UUID, item: NetworthAssetCreate) -> NetworthAssetOut:
    new_id = str(uuid4())
    db.execute(
        text("INSERT INTO networth_assets (id, user_id, name, category, balance) VALUES (:id, :uid, :name, :cat, :bal)"),
        {"id": new_id, "uid": str(user_id), "name": item.name, "cat": item.category, "bal": item.balance},
    )
    db.commit()
    return NetworthAssetOut(id=new_id, name=item.name, category=item.category, balance=item.balance)


def update_asset(db: Session, user_id: UUID, asset_id: str, item: NetworthAssetUpdate) -> Optional[NetworthAssetOut]:
    fields, params = [], {"uid": str(user_id), "asset_id": asset_id}
    if item.name is not None:
        fields.append("name = :name"); params["name"] = item.name
    if item.category is not None:
        fields.append("category = :cat"); params["cat"] = item.category
    if item.balance is not None:
        fields.append("balance = :bal"); params["bal"] = item.balance
    if not fields:
        return None
    fields.append("updated_at = CURRENT_TIMESTAMP")
    result = db.execute(
        text(f"UPDATE networth_assets SET {', '.join(fields)} WHERE id = :asset_id AND user_id = :uid"),
        params,
    )
    db.commit()
    if result.rowcount == 0:
        return None
    row = db.execute(
        text("SELECT id, name, category, balance, updated_at FROM networth_assets WHERE id = :id"),
        {"id": asset_id},
    ).fetchone()
    if not row:
        return None
    d = row_to_dict(row)
    return NetworthAssetOut(
        id=str(d["id"]), name=d["name"], category=d["category"],
        balance=safe_float(d["balance"], 0.0) or 0.0,
        updated_at=safe_datetime_to_str(d["updated_at"]),
    )


def delete_asset(db: Session, user_id: UUID, asset_id: str) -> bool:
    result = db.execute(
        text("DELETE FROM networth_assets WHERE id = :asset_id AND user_id = :uid"),
        {"asset_id": asset_id, "uid": str(user_id)},
    )
    db.commit()
    return result.rowcount > 0


# ---------------------------------------------------------------------------
# Liability CRUD
# ---------------------------------------------------------------------------

def get_liabilities(db: Session, user_id: UUID) -> List[NetworthLiabilityOut]:
    rows = db.execute(
        text("SELECT id, name, category, balance, updated_at FROM networth_liabilities WHERE user_id = :uid ORDER BY created_at ASC"),
        {"uid": str(user_id)},
    ).fetchall()
    result = []
    for row in rows:
        d = row_to_dict(row)
        result.append(NetworthLiabilityOut(
            id=str(d["id"]),
            name=d["name"],
            category=d["category"],
            balance=safe_float(d["balance"], 0.0) or 0.0,
            updated_at=safe_datetime_to_str(d["updated_at"]),
        ))
    return result


def add_liability(db: Session, user_id: UUID, item: NetworthLiabilityCreate) -> NetworthLiabilityOut:
    new_id = str(uuid4())
    db.execute(
        text("INSERT INTO networth_liabilities (id, user_id, name, category, balance) VALUES (:id, :uid, :name, :cat, :bal)"),
        {"id": new_id, "uid": str(user_id), "name": item.name, "cat": item.category, "bal": item.balance},
    )
    db.commit()
    return NetworthLiabilityOut(id=new_id, name=item.name, category=item.category, balance=item.balance)


def update_liability(db: Session, user_id: UUID, liability_id: str, item: NetworthLiabilityUpdate) -> Optional[NetworthLiabilityOut]:
    fields, params = [], {"uid": str(user_id), "lid": liability_id}
    if item.name is not None:
        fields.append("name = :name"); params["name"] = item.name
    if item.category is not None:
        fields.append("category = :cat"); params["cat"] = item.category
    if item.balance is not None:
        fields.append("balance = :bal"); params["bal"] = item.balance
    if not fields:
        return None
    fields.append("updated_at = CURRENT_TIMESTAMP")
    result = db.execute(
        text(f"UPDATE networth_liabilities SET {', '.join(fields)} WHERE id = :lid AND user_id = :uid"),
        params,
    )
    db.commit()
    if result.rowcount == 0:
        return None
    row = db.execute(
        text("SELECT id, name, category, balance, updated_at FROM networth_liabilities WHERE id = :id"),
        {"id": liability_id},
    ).fetchone()
    if not row:
        return None
    d = row_to_dict(row)
    return NetworthLiabilityOut(
        id=str(d["id"]), name=d["name"], category=d["category"],
        balance=safe_float(d["balance"], 0.0) or 0.0,
        updated_at=safe_datetime_to_str(d["updated_at"]),
    )


def delete_liability(db: Session, user_id: UUID, liability_id: str) -> bool:
    result = db.execute(
        text("DELETE FROM networth_liabilities WHERE id = :lid AND user_id = :uid"),
        {"lid": liability_id, "uid": str(user_id)},
    )
    db.commit()
    return result.rowcount > 0
