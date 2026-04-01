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


class AlertOut(BaseModel):
    id: str
    ticker: str
    target_price: float
    direction: str
    is_active: bool
    triggered_at: Optional[str]
    created_at: Optional[str]

    class Config:
        from_attributes = True


@router.get("", response_model=List[AlertOut])
def list_alerts(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[AlertOut]:
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
            triggered_at=a.triggered_at.isoformat() if a.triggered_at else None,
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
        triggered_at=None,
        created_at=alert.created_at.isoformat() if alert.created_at else None,
    )


@router.delete("/{alert_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_alert(
    alert_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    alert = (
        db.query(PriceAlert)
        .filter(PriceAlert.id == alert_id, PriceAlert.user_id == current_user.id)
        .first()
    )
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    db.delete(alert)
    db.commit()
