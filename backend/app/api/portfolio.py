from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.main import get_db
from app.services.portfolio_service import portfolio_service
from app.schema.schemas import PortfolioCreateItem, PortfolioUpdateItem
from app.models.portfolio_model import PortfolioItemModel

router = APIRouter(prefix="/portfolio", tags=["Portfolio"])

@router.post("/{user_id}add", response_model=PortfolioItemModel)
def add_item(
	user_id: UUID, 
	data: PortfolioCreateItem, 
	db: Session = Depends(get_db)
):
	return portfolio_service.add_item(
		db=db, 
		user_id=user_id, 
		data=data
	)

@router.get("/{user_id}", response_model=list[PortfolioItemModel])
def get_items(
	user_id: UUID, 
	db: Session = Depends(get_db)
):
	return portfolio_service.get_items(db=db, user_id=user_id)

@router.put("/{user_id}/{item_id}", response_model=PortfolioItemModel)
def update_item(
	user_id: UUID,
	item_id: UUID,
	data: PortfolioUpdateItem,
	db: Session = Depends(get_db)
):
    try:
        return portfolio_service.update_item(
            db=db,
            user_id=user_id,
            item_id=item_id,
            data=data
    )
    except HTTPException as e:
        raise e
    
@router.delete("/{user_id}/{item_id}")
def delete_item(
	user_id: UUID, 
	item_id: UUID, 
	db: Session = Depends(get_db)
):
	try:
		return portfolio_service.delete_item(
			db=db, 
			user_id=user_id, 
			item_id=item_id
		)
	except HTTPException as e:
		raise e