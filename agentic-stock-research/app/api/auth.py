# Authentication API Endpoints

from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import HTTPBearer
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime

from app.auth.user_manager import (
    get_user_manager, get_auth_manager, get_current_user, get_current_user_optional,
    register_user, login_user, logout_user, User, UserPreferences
)

router = APIRouter(prefix="/auth", tags=["authentication"])
security = HTTPBearer()

# Pydantic models for request/response
class UserRegister(BaseModel):
    email: str
    username: str
    full_name: str
    password: str

class UserLogin(BaseModel):
    email: str  # This field accepts both email and username
    password: str

class UserResponse(BaseModel):
    id: str
    email: str
    username: str
    full_name: str
    created_at: str
    last_login: Optional[str] = None
    is_premium: bool = False

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse

class UserPreferencesUpdate(BaseModel):
    default_country: Optional[str] = None
    default_timeframe: Optional[str] = None
    chart_theme: Optional[str] = None
    notifications_enabled: Optional[bool] = None
    email_alerts: Optional[bool] = None
    sms_alerts: Optional[bool] = None
    preferred_sectors: Optional[List[str]] = None
    risk_tolerance: Optional[str] = None
    investment_horizon: Optional[str] = None

class WatchlistUpdate(BaseModel):
    ticker: str

class PortfolioCreate(BaseModel):
    name: str

@router.post("/register", response_model=TokenResponse)
async def register(user_data: UserRegister):
    """Register a new user"""
    try:
        result = register_user(
            email=user_data.email,
            username=user_data.username,
            full_name=user_data.full_name,
            password=user_data.password
        )
        return TokenResponse(**result)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed"
        )

@router.post("/login", response_model=TokenResponse)
async def login(login_data: UserLogin):
    """Login user"""
    try:
        result = login_user(email_or_username=login_data.email, password=login_data.password)
        return TokenResponse(**result)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed"
        )

@router.post("/logout")
async def logout(current_user: User = Depends(get_current_user)):
    """Logout user"""
    auth_manager = get_auth_manager()
    revoked_count = auth_manager.revoke_all_user_tokens(current_user.id)
    
    return {
        "message": "Successfully logged out",
        "revoked_tokens": revoked_count
    }

@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current user information"""
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        username=current_user.username,
        full_name=current_user.full_name,
        created_at=current_user.created_at.isoformat(),
        last_login=current_user.last_login.isoformat() if current_user.last_login else None,
        is_premium=current_user.is_premium
    )

@router.get("/preferences")
async def get_user_preferences(current_user: User = Depends(get_current_user)):
    """Get user preferences"""
    user_manager = get_user_manager()
    preferences = user_manager.user_preferences.get(current_user.id)
    
    if not preferences:
        return UserPreferencesUpdate()
    
    return {
        "default_country": preferences.default_country,
        "default_timeframe": preferences.default_timeframe,
        "chart_theme": preferences.chart_theme,
        "notifications_enabled": preferences.notifications_enabled,
        "email_alerts": preferences.email_alerts,
        "sms_alerts": preferences.sms_alerts,
        "preferred_sectors": preferences.preferred_sectors or [],
        "risk_tolerance": preferences.risk_tolerance,
        "investment_horizon": preferences.investment_horizon
    }

@router.put("/preferences")
async def update_user_preferences(
    preferences: UserPreferencesUpdate,
    current_user: User = Depends(get_current_user)
):
    """Update user preferences"""
    user_manager = get_user_manager()
    
    # Convert to dict, excluding None values
    prefs_dict = {k: v for k, v in preferences.dict().items() if v is not None}
    
    success = user_manager.update_user_preferences(current_user.id, prefs_dict)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to update preferences"
        )
    
    return {"message": "Preferences updated successfully"}

@router.get("/watchlist")
async def get_watchlist(current_user: User = Depends(get_current_user)):
    """Get user's watchlist"""
    user_manager = get_user_manager()
    watchlist = user_manager.get_user_watchlist(current_user.id)
    
    return {
        "watchlist": watchlist,
        "count": len(watchlist)
    }

@router.post("/watchlist")
async def add_to_watchlist(
    ticker_data: WatchlistUpdate,
    current_user: User = Depends(get_current_user)
):
    """Add ticker to watchlist"""
    user_manager = get_user_manager()
    success = user_manager.add_to_watchlist(current_user.id, ticker_data.ticker)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to add ticker to watchlist"
        )
    
    return {"message": f"Added {ticker_data.ticker} to watchlist"}

@router.delete("/watchlist/{ticker}")
async def remove_from_watchlist(
    ticker: str,
    current_user: User = Depends(get_current_user)
):
    """Remove ticker from watchlist"""
    user_manager = get_user_manager()
    success = user_manager.remove_from_watchlist(current_user.id, ticker)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to remove ticker from watchlist"
        )
    
    return {"message": f"Removed {ticker} from watchlist"}

@router.get("/portfolios")
async def get_portfolios(current_user: User = Depends(get_current_user)):
    """Get user's portfolios"""
    user_manager = get_user_manager()
    portfolios = user_manager.get_user_portfolios(current_user.id)
    
    return {
        "portfolios": portfolios,
        "count": len(portfolios)
    }

@router.post("/portfolios")
async def create_portfolio(
    portfolio_data: PortfolioCreate,
    current_user: User = Depends(get_current_user)
):
    """Create a new portfolio"""
    user_manager = get_user_manager()
    success = user_manager.create_portfolio(current_user.id, portfolio_data.name)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to create portfolio"
        )
    
    return {"message": f"Created portfolio: {portfolio_data.name}"}

@router.get("/profile")
async def get_user_profile(current_user: User = Depends(get_current_user)):
    """Get comprehensive user profile"""
    user_manager = get_user_manager()
    
    return {
        "user": {
            "id": current_user.id,
            "email": current_user.email,
            "username": current_user.username,
            "full_name": current_user.full_name,
            "created_at": current_user.created_at.isoformat(),
            "last_login": current_user.last_login.isoformat() if current_user.last_login else None,
            "is_premium": current_user.is_premium,
            "is_active": current_user.is_active
        },
        "preferences": user_manager.user_preferences.get(current_user.id, {}),
        "watchlist": user_manager.get_user_watchlist(current_user.id),
        "portfolios": user_manager.get_user_portfolios(current_user.id),
        "stats": {
            "watchlist_count": len(user_manager.get_user_watchlist(current_user.id)),
            "portfolio_count": len(user_manager.get_user_portfolios(current_user.id)),
            "account_age_days": (datetime.now() - current_user.created_at).days
        }
    }