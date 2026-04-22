"""
Price Alerts API endpoints
"""
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.db.main import get_db
from app.models.models import PriceAlert, User

router = APIRouter()


class AlertCreate(BaseModel):
    ticker: str
    target_price: float
    direction: str  # "above" or "below"
    email_notify: bool = True


class AlertOut(BaseModel):
    id: str
    ticker: str
    target_price: float
    direction: str
    is_active: bool
    email_notify: bool
    triggered_at: Optional[str]
    triggered_price: Optional[float]
    created_at: Optional[str]

    class Config:
        from_attributes = True


@router.get("", response_model=List[AlertOut])
def list_alerts(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[AlertOut]:
    """
    Return all price alerts for the authenticated user, ordered newest first.

    Returns
    -------
    list of AlertOut
        Active and triggered alerts belonging to the current user.
    """
    alerts = (
        db.query(PriceAlert)
        .filter(PriceAlert.user_id == current_user.id)
        .order_by(PriceAlert.created_at.desc())
        .all()
    )
    return [
        AlertOut(
            id=str(a.id),
            ticker=a.ticker,
            target_price=float(a.target_price),
            direction=a.direction,
            is_active=a.is_active,
            email_notify=a.email_notify,
            triggered_at=a.triggered_at.isoformat() if a.triggered_at else None,
            triggered_price=float(a.triggered_price) if a.triggered_price is not None else None,
            created_at=a.created_at.isoformat() if a.created_at else None,
        )
        for a in alerts
    ]


@router.post("", response_model=AlertOut, status_code=status.HTTP_201_CREATED)
def create_alert(
    body: AlertCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AlertOut:
    """
    Create a new price alert for the authenticated user.

    Notes
    -----
    Direction must be 'above' or 'below'. Target price must be positive.
    The ticker is normalized to uppercase before storage. The alert becomes
    active immediately and will trigger when the stock price crosses the
    target in the specified direction.

    Returns
    -------
    AlertOut
        The newly created alert record.
    """
    if body.direction not in ("above", "below"):
        raise HTTPException(status_code=400, detail="direction must be 'above' or 'below'")
    if body.target_price <= 0:
        raise HTTPException(status_code=400, detail="target_price must be positive")

    alert = PriceAlert(
        id=uuid.uuid4(),
        user_id=current_user.id,
        ticker=body.ticker.upper(),
        target_price=body.target_price,
        direction=body.direction,
        is_active=True,
        email_notify=body.email_notify,
        created_at=datetime.now(timezone.utc),
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)

    return AlertOut(
        id=str(alert.id),
        ticker=alert.ticker,
        target_price=float(alert.target_price),
        direction=alert.direction,
        is_active=alert.is_active,
        email_notify=alert.email_notify,
        triggered_at=None,
        triggered_price=None,
        created_at=alert.created_at.isoformat() if alert.created_at else None,
    )


@router.delete("/{alert_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_alert(
    alert_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """
    Permanently delete a price alert owned by the authenticated user.

    Path Parameters
    ---------------
    alert_id : str
        UUID of the alert to delete.

    Notes
    -----
    Returns 404 if the alert does not exist or belongs to a different user.
    """
    alert = (
        db.query(PriceAlert)
        .filter(PriceAlert.id == alert_id, PriceAlert.user_id == current_user.id)
        .first()
    )
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    db.delete(alert)
    db.commit()
