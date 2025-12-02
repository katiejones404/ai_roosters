import os
import sys
from uuid import UUID
from fastapi import HHTPException, status
from sqlalchemy import Session
from backend.app.models.portfolio_model import PortfolioItemModel
from backend.app.schema.portfolio_schema import PortfolioCreateItem, PortfolioUpdateItem

class portfolio_service:

    @staticmethod
    def add_item(db:Session, user_id:UUID, data: PortfolioCreateItem):
        item = PortfolioItemModel(
            user_id=user_id,
            ticker=data.ticker.upper(),
            quantity=data.quantity,
            avg_price=data.avg_price
        )

        db.add(item)
        db.commit()
        db.refresh(item)
        return item

    @staticmethod
    def get_items(db: Session, user_id: UUID):
        return (
            db.query(PortfolioItemModel)
            .filter(PortfolioItemModel.user_id == user_id)
            .order_by(PortfolioItemModel.added_at.desc())
            .all()
        )
    
    @staticmethod
    def update_item(db: Session, user_id: UUID, item_id: UUID, data: PortfolioItemModel):
        item = (
            db.query(PortfolioItemModel)
            .filter(
                PortfolioItemModel.id == item_id,
                PortfolioItemModel.user_id == user_id
            )
            .first()
        )

        if not item:
            raise HHTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio item not found")
        if data.quantity is not None:
            item.quantity = data.quantity
        if data.avg_price is not None:
            item.avg_price = data.avg_price

        db.commit()
        db.refresh(item)
        return item
    
    @staticmethod
    def delete_item(db: Session, user_id: UUID, item_id: UUID):
        item = (
            db.query(PortfolioItemModel)
            .filter(
                PortfolioItemModel.id == item_id,
                PortfolioItemModel.user_id == user_id
            )
            .first()
        )

        if not item:
            raise HHTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio item not found")
        
        db.delete(item)
        db.commit()
        return {"message": "Item deleted"}