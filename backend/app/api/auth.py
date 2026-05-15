"""
Authentication API endpoints for StockSense.

Handles user registration, login, logout, profile management, password reset,
daily streak tracking, and notification preferences. All protected routes
require a valid JWT token issued at login.
"""
import os
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import func, or_
from sqlalchemy.orm import Session
from datetime import timedelta, date
from typing import Annotated
import re
import asyncio
import json

# Import using sys.path approach for Docker compatibility
import sys
sys.path.insert(0, '/app')

from app.db.main import get_db
from app.models.models import User
from app.schema.schemas import (
    UserRegister,
    UserLogin,
    UserResponse,
    Token,
    ProfilePictureUpdate,
    DeleteAccountRequest,
    UserProfileUpdate,
    PasswordChange,
    StreakResponse,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    NotificationPreferencesResponse,
    NotificationPreferencesUpdate,
)
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    verify_token,
    oauth2_scheme,
    ACCESS_TOKEN_EXPIRE_MINUTES
)
from app.services.email_service import send_password_reset_email

router = APIRouter(prefix="/auth", tags=["auth"])
_DEFAULT_PROFILE_PICTURE_FALLBACK = "/default_pfp.jpg"


def _resolve_default_profile_picture() -> str:
    configured = (os.getenv("DEFAULT_PROFILE_PICTURE") or "").strip()
    if not configured:
        return _DEFAULT_PROFILE_PICTURE_FALLBACK

    lowered = configured.lower()
    # Guard against common typo/misconfiguration values from env.
    if lowered.endswith("default_pfp.jgp") or lowered.endswith("default_pfp.jpeg"):
        return _DEFAULT_PROFILE_PICTURE_FALLBACK

    return configured


DEFAULT_PROFILE_PICTURE = _resolve_default_profile_picture()

# --- Token Blacklist (Feature #6) ---
# In-memory set of invalidated tokens. Resets on server restart.
token_blacklist: set[str] = set()


def _normalize_visit_days(raw: str | None) -> list[str]:
    """Parse the JSON-encoded visit-day list stored on the user record into a plain list of date strings."""
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
        if not isinstance(parsed, list):
            return []
        return [d for d in parsed if isinstance(d, str) and d]
    except Exception:
        return []


def _serialize_streak(current_user: User) -> StreakResponse:
    """Compute and update the user's daily login streak, then return the current streak data."""
    today = date.today()
    today_s = today.isoformat()

    current = current_user.streak_current if isinstance(current_user.streak_current, int) and current_user.streak_current > 0 else 1
    best = current_user.streak_best if isinstance(current_user.streak_best, int) and current_user.streak_best > 0 else current
    total = current_user.streak_total_visits if isinstance(current_user.streak_total_visits, int) and current_user.streak_total_visits > 0 else 1
    last_visit_date = current_user.streak_last_visit if isinstance(current_user.streak_last_visit, date) else today
    visit_days = _normalize_visit_days(current_user.streak_visit_days)

    if not visit_days:
        visit_days = [last_visit_date.isoformat()]

    diff_days = (today - last_visit_date).days
    if diff_days == 1:
        current += 1
        best = max(best, current)
        total += 1
        last_visit_date = today
        if today_s not in visit_days:
            visit_days.append(today_s)
    elif diff_days > 1:
        current = 1
        total += 1
        last_visit_date = today
        if today_s not in visit_days:
            visit_days.append(today_s)

    visit_days = visit_days[-365:]
    best = max(best, current)
    total = max(total, len(visit_days))

    current_user.streak_current = current
    current_user.streak_best = best
    current_user.streak_last_visit = last_visit_date
    current_user.streak_visit_days = json.dumps(visit_days)
    current_user.streak_total_visits = total

    return StreakResponse(
        currentStreak=current,
        bestStreak=best,
        lastVisit=last_visit_date.isoformat(),
        visitDays=visit_days,
        totalVisits=total,
    )


def _serialize_notification_preferences(current_user: User) -> NotificationPreferencesResponse:
    """Build a notification preferences response from the user's stored column values."""
    return NotificationPreferencesResponse(
        marketAlerts=bool(
            True if current_user.notify_market_alerts_enabled is None else current_user.notify_market_alerts_enabled
        ),
        pushNotifications=bool(
            False if current_user.notify_push_enabled is None else current_user.notify_push_enabled
        ),
    )


def _needs_default_profile_picture(profile_picture: str | None) -> bool:
    """
    Return True when the profile picture should be replaced with the app default.

    This treats empty values and legacy random Dicebear URLs as needing the
    default image, while preserving user-uploaded/custom pictures.
    """
    if not profile_picture or not profile_picture.strip():
        return True
    lowered = profile_picture.strip().lower()
    if "dicebear.com" in lowered:
        return True
    if lowered.endswith("default_pfp.jgp") or lowered.endswith("default_pfp.jpeg"):
        return True
    return False


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(user_data: UserRegister, db: Session = Depends(get_db)):
    """Register a new user"""

    # --- Feature #2: Username character validation ---
    if not re.match(r'^[a-zA-Z0-9_]+$', user_data.username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username can only contain letters, numbers, and underscores."
        )

    # Check if email already exists
    existing_user = db.query(User).filter(User.email == user_data.email.lower()).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists."
        )

    # Check if username already exists
    existing_username = db.query(User).filter(User.username == user_data.username).first()
    if existing_username:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this username already exists."
        )

    # Password strength validation
    if len(user_data.password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters."
        )
    if not re.search(r'[0-9!@#$%^&*(),.?\":{}|<>]', user_data.password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must contain at least one number or special character."
        )

    # Create new user
    hashed_password = hash_password(user_data.password)
    new_user = User(
        username=user_data.username,
        email=user_data.email.lower(),
        password_hash=hashed_password,
        profile_picture=DEFAULT_PROFILE_PICTURE,
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return new_user


@router.post("/login", response_model=Token)
async def login(user_data: UserLogin, db: Session = Depends(get_db)):
    """Login user and return JWT token"""
    # The login field accepts either email or username for convenience.
    login_identifier = user_data.email.strip().lower()
    user = (
        db.query(User)
        .filter(
            or_(
                func.lower(User.email) == login_identifier,
                func.lower(User.username) == login_identifier,
            )
        )
        .first()
    )

    if not user or not verify_password(user_data.password, user.password_hash):
        # --- Feature #3: Delay on failed login to slow brute-force attacks ---
        await asyncio.sleep(1)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Normalize legacy/random avatars to the app's default profile picture.
    if _needs_default_profile_picture(user.profile_picture):
        user.profile_picture = DEFAULT_PROFILE_PICTURE
        db.commit()

    # Create access token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )

    return {"access_token": access_token, "token_type": "bearer"}


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Session = Depends(get_db)
) -> User:
    """Get current user from JWT token"""

    # --- Feature #6: Reject blacklisted tokens ---
    if token in token_blacklist:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been invalidated. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = verify_token(token)
    email = payload.get("sub")
    if email is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.query(User).filter(User.email == email).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )

    return user


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current user information"""
    return current_user


@router.get("/me/streak", response_model=StreakResponse)
async def get_current_user_streak(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get and update the authenticated user's daily streak."""
    streak = _serialize_streak(current_user)
    db.commit()
    return streak


@router.get("/me/notifications", response_model=NotificationPreferencesResponse)
async def get_notification_preferences(current_user: User = Depends(get_current_user)):
    """Get persisted notification preferences for the authenticated user."""
    return _serialize_notification_preferences(current_user)


@router.patch("/me/notifications", response_model=NotificationPreferencesResponse)
async def update_notification_preferences(
    data: NotificationPreferencesUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update persisted notification preferences for the authenticated user."""
    if (
        data.marketAlerts is None
        and data.pushNotifications is None
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one notification preference is required.",
        )

    if data.marketAlerts is not None:
        current_user.notify_market_alerts_enabled = data.marketAlerts
    if data.pushNotifications is not None:
        current_user.notify_push_enabled = data.pushNotifications

    db.commit()
    db.refresh(current_user)
    return _serialize_notification_preferences(current_user)


@router.post("/logout")
async def logout(token: Annotated[str, Depends(oauth2_scheme)]):
    """
    Logout user by blacklisting their token.
    The client should also delete the token locally.
    """
    # --- Feature #6: Add token to blacklist ---
    token_blacklist.add(token)
    return {"message": "Successfully logged out. Your session has been invalidated."}


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    data: DeleteAccountRequest,
    token: Annotated[str, Depends(oauth2_scheme)],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Permanently delete the authenticated user's account and all associated data.
    Requires the user's current password for confirmation.
    Cascades to portfolio rows via the foreign key constraint.
    """
    if not verify_password(data.password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect password."
        )
    db.delete(current_user)
    db.commit()
    token_blacklist.add(token)


@router.put("/me/picture", response_model=UserResponse)
async def update_profile_picture(
    data: ProfilePictureUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update the authenticated user's profile picture"""
    profile_picture = (data.profile_picture or "").strip()
    current_user.profile_picture = profile_picture or DEFAULT_PROFILE_PICTURE
    db.commit()
    db.refresh(current_user)
    return current_user


@router.patch("/me", response_model=UserResponse)
async def update_profile(
    data: UserProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update the authenticated user's name, username, and/or phone number"""
    if data.username is not None:
        existing = db.query(User).filter(
            User.username == data.username,
            User.id != current_user.id
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Username already taken."
            )
        current_user.username = data.username
    if data.name is not None:
        current_user.name = data.name
    if data.phone is not None:
        current_user.phone = data.phone
    db.commit()
    db.refresh(current_user)
    return current_user


@router.patch("/me/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    data: PasswordChange,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Change the authenticated user's password"""
    if not verify_password(data.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect."
        )
    if len(data.new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters."
        )
    if not re.search(r'[0-9!@#$%^&*(),.?\":{}|<>]', data.new_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must contain at least one number or special character."
        )
    current_user.password_hash = hash_password(data.new_password)
    db.commit()


@router.post("/forgot-password", status_code=status.HTTP_204_NO_CONTENT)
def forgot_password(data: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """
    Send a password reset email if the provided email matches a registered account.

    Notes
    -----
    Always returns 204 regardless of whether the email exists to prevent
    user enumeration attacks.

    Path Parameters
    ---------------
    data : ForgotPasswordRequest
        Body containing the user's email address.
    """
    user = db.query(User).filter(User.email == data.email.lower()).first()
    if not user:
        return  # Silent no-op to prevent enumeration

    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/")
    reset_token = create_access_token(
        data={"sub": user.email, "type": "password_reset"},
        expires_delta=timedelta(minutes=15),
    )
    reset_link = f"{frontend_url}/reset-password?token={reset_token}"

    try:
        send_password_reset_email(user.email, reset_link)
    except Exception:
        # Log but do not expose errors to the caller
        pass


@router.post("/reset-password", status_code=status.HTTP_204_NO_CONTENT)
def reset_password(data: ResetPasswordRequest, db: Session = Depends(get_db)):
    """
    Reset a user's password using a valid password reset token.

    Parameters
    ----------
    data : ResetPasswordRequest
        Body containing the reset token and the new password.

    Returns
    -------
    None
        Returns 204 on success. Returns 400 if the token is invalid or expired.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Invalid or expired reset token.",
    )
    try:
        payload = verify_token(data.token)
    except HTTPException:
        raise credentials_exception

    if payload.get("type") != "password_reset":
        raise credentials_exception

    email = payload.get("sub")
    if not email:
        raise credentials_exception

    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise credentials_exception

    if len(data.new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters.",
        )
    if not re.search(r'[0-9!@#$%^&*(),.?\":{}|<>]', data.new_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must contain at least one number or special character.",
        )

    user.password_hash = hash_password(data.new_password)
    db.commit()
