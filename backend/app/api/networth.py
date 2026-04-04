"""
Net Worth API endpoints for managing assets, liabilities, and historical snapshots.

Notes
-----
All endpoints require authentication. Assets and liabilities are stored per user.
Net worth is calculated as total assets minus total liabilities.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import List
import sys

sys.path.insert(0, '/app')

from app.db.main import get_db
from app.models.models import User
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
from app.api.auth import get_current_user
from app.services import networth

router = APIRouter(prefix="/networth", tags=["networth"])


# ---------------------------------------------------------------------------
# Summary + snapshot
# ---------------------------------------------------------------------------

@router.get("", response_model=NetworthSummary)
async def get_networth_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Return the current net worth summary for the authenticated user.

    Returns
    -------
    NetworthSummary
        Aggregated total assets, total liabilities, portfolio value, and net worth.
    """
    return networth.get_summary(db, current_user.id)


@router.post("/snapshot", status_code=status.HTTP_204_NO_CONTENT)
async def record_snapshot(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Save a point-in-time net worth snapshot for the current user.

    Notes
    -----
    Snapshots are used to build the net worth history chart. One snapshot
    per day is recommended. Calling this endpoint multiple times on the same
    day will create multiple records.
    """
    networth.record_snapshot(db, current_user.id)


@router.get("/history", response_model=List[NetworthSnapshotOut])
async def get_history(
    days: int = Query(default=30, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Return net worth snapshots for the past N days.

    Query Parameters
    ----------------
    days : int
        Number of days of history to return. Minimum 1, maximum 365. Default 30.

    Returns
    -------
    list of NetworthSnapshotOut
        Snapshots ordered chronologically, newest last.
    """
    return networth.get_history(db, current_user.id, days)


# ---------------------------------------------------------------------------
# Assets
# ---------------------------------------------------------------------------

@router.get("/assets", response_model=List[NetworthAssetOut])
async def list_assets(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Return all assets for the authenticated user.

    Returns
    -------
    list of NetworthAssetOut
        All asset records belonging to the current user.
    """
    return networth.get_assets(db, current_user.id)


@router.post("/assets", response_model=NetworthAssetOut, status_code=status.HTTP_201_CREATED)
async def add_asset(
    item: NetworthAssetCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create a new asset for the authenticated user.

    Returns
    -------
    NetworthAssetOut
        The newly created asset record.
    """
    return networth.add_asset(db, current_user.id, item)


@router.put("/assets/{asset_id}", response_model=NetworthAssetOut)
async def update_asset(
    asset_id: str,
    item: NetworthAssetUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Update an existing asset by ID for the authenticated user.

    Path Parameters
    ---------------
    asset_id : str
        UUID of the asset to update.

    Returns
    -------
    NetworthAssetOut
        The updated asset record.

    Notes
    -----
    Returns 404 if the asset does not exist or belongs to a different user.
    """
    updated = networth.update_asset(db, current_user.id, asset_id, item)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")
    return updated


@router.delete("/assets/{asset_id}")
async def delete_asset(
    asset_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Permanently remove an asset by ID for the authenticated user.

    Path Parameters
    ---------------
    asset_id : str
        UUID of the asset to delete.

    Notes
    -----
    Returns 404 if the asset does not exist or belongs to a different user.
    """
    if not networth.delete_asset(db, current_user.id, asset_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")
    return {"status": "ok", "message": "Asset deleted"}


# ---------------------------------------------------------------------------
# Liabilities
# ---------------------------------------------------------------------------

@router.get("/liabilities", response_model=List[NetworthLiabilityOut])
async def list_liabilities(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Return all liabilities for the authenticated user.

    Returns
    -------
    list of NetworthLiabilityOut
        All liability records belonging to the current user.
    """
    return networth.get_liabilities(db, current_user.id)


@router.post("/liabilities", response_model=NetworthLiabilityOut, status_code=status.HTTP_201_CREATED)
async def add_liability(
    item: NetworthLiabilityCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create a new liability for the authenticated user.

    Returns
    -------
    NetworthLiabilityOut
        The newly created liability record.
    """
    return networth.add_liability(db, current_user.id, item)


@router.put("/liabilities/{liability_id}", response_model=NetworthLiabilityOut)
async def update_liability(
    liability_id: str,
    item: NetworthLiabilityUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Update an existing liability by ID for the authenticated user.

    Path Parameters
    ---------------
    liability_id : str
        UUID of the liability to update.

    Returns
    -------
    NetworthLiabilityOut
        The updated liability record.

    Notes
    -----
    Returns 404 if the liability does not exist or belongs to a different user.
    """
    updated = networth.update_liability(db, current_user.id, liability_id, item)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Liability not found")
    return updated


@router.delete("/liabilities/{liability_id}")
async def delete_liability(
    liability_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Permanently remove a liability by ID for the authenticated user.

    Path Parameters
    ---------------
    liability_id : str
        UUID of the liability to delete.

    Notes
    -----
    Returns 404 if the liability does not exist or belongs to a different user.
    """
    if not networth.delete_liability(db, current_user.id, liability_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Liability not found")
    return {"status": "ok", "message": "Liability deleted"}
