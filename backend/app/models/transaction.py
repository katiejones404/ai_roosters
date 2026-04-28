"""SQLAlchemy ORM model for user trade transactions in StockSense."""
import uuid
from sqlalchemy import Column, String, Date, Numeric, ForeignKey, TIMESTAMP
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.base import Base
from app.db.types import GUID


class Transaction(Base):
    """Records a single buy or sell trade event for a user, including realized gain on sells."""
    __tablename__ = "transactions"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id = Column(GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    ticker = Column(String, nullable=False)
    action = Column(String, nullable=False)  # "buy" or "sell"
    quantity = Column(Numeric, nullable=False)
    price = Column(Numeric, nullable=False)
    realized_gain = Column(Numeric, nullable=True)
    trade_date = Column(Date, nullable=True)  # <-- IMPORTANT
    executed_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    user = relationship("User")