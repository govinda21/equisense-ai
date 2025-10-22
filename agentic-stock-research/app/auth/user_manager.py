# User Authentication & Personalization System

from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from passlib.context import CryptContext
from jose import JWTError, jwt
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import logging

logger = logging.getLogger(__name__)

# Security configuration
SECRET_KEY = "your-secret-key-here"  # Should be in environment variables
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

@dataclass
class User:
    """User data structure"""
    id: str
    email: str
    username: str
    full_name: str
    created_at: datetime
    last_login: Optional[datetime] = None
    preferences: Optional[Dict[str, Any]] = None
    watchlists: Optional[List[str]] = None
    portfolios: Optional[List[str]] = None
    is_active: bool = True
    is_premium: bool = False

@dataclass
class UserPreferences:
    """User preferences structure"""
    default_country: str = "India"
    default_timeframe: str = "1M"
    chart_theme: str = "light"
    notifications_enabled: bool = True
    email_alerts: bool = True
    sms_alerts: bool = False
    preferred_sectors: List[str] = None
    risk_tolerance: str = "moderate"
    investment_horizon: str = "long_term"

class UserManager:
    """User management system"""
    
    def __init__(self):
        self.users: Dict[str, User] = {}
        self.user_preferences: Dict[str, UserPreferences] = {}
        self.user_sessions: Dict[str, str] = {}  # token -> user_id
        
        # Create default admin user for development
        self._create_default_admin()
    
    def _create_default_admin(self):
        """Create default admin user for development"""
        admin_user = User(
            id="admin",
            email="admin@equisense.ai",
            username="admin",
            full_name="Admin User",
            created_at=datetime.now(),
            preferences={},
            watchlists=[],
            portfolios=[],
            is_premium=True
        )
        self.users["admin"] = admin_user
        self.user_preferences["admin"] = UserPreferences()
        logger.info("Created default admin user: admin")
    
    def create_user(self, email: str, username: str, full_name: str, password: str) -> User:
        """Create a new user"""
        user_id = f"user_{len(self.users) + 1}"
        
        # Check if user already exists
        if any(user.email == email or user.username == username for user in self.users.values()):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User with this email or username already exists"
            )
        
        # Create user
        user = User(
            id=user_id,
            email=email,
            username=username,
            full_name=full_name,
            created_at=datetime.now(),
            preferences={},
            watchlists=[],
            portfolios=[]
        )
        
        self.users[user_id] = user
        self.user_preferences[user_id] = UserPreferences()
        
        logger.info(f"Created user: {user_id} ({email})")
        return user
    
    def authenticate_user(self, email_or_username: str, password: str) -> Optional[User]:
        """Authenticate user with email or username and password"""
        user = self._get_user_by_email_or_username(email_or_username)
        if not user:
            return None
        
        # In a real implementation, you would verify the password hash
        # For now, we'll use a simple check
        if password == "admin" or password == "password123" or password == "admin123":  # This should be hashed and verified
            user.last_login = datetime.now()
            return user
        
        return None
    
    def _get_user_by_email_or_username(self, email_or_username: str) -> Optional[User]:
        """Get user by email or username"""
        for user in self.users.values():
            if user.email == email_or_username or user.username == email_or_username:
                return user
        return None
    
    def _get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email"""
        for user in self.users.values():
            if user.email == email:
                return user
        return None
    
    def get_user_by_id(self, user_id: str) -> Optional[User]:
        """Get user by ID"""
        return self.users.get(user_id)
    
    def update_user_preferences(self, user_id: str, preferences: Dict[str, Any]) -> bool:
        """Update user preferences"""
        if user_id not in self.users:
            return False
        
        user = self.users[user_id]
        if user.preferences is None:
            user.preferences = {}
        
        user.preferences.update(preferences)
        
        # Update UserPreferences object
        if user_id in self.user_preferences:
            pref_obj = self.user_preferences[user_id]
            for key, value in preferences.items():
                if hasattr(pref_obj, key):
                    setattr(pref_obj, key, value)
        
        logger.info(f"Updated preferences for user: {user_id}")
        return True
    
    def add_to_watchlist(self, user_id: str, ticker: str) -> bool:
        """Add ticker to user's watchlist"""
        if user_id not in self.users:
            return False
        
        user = self.users[user_id]
        if user.watchlists is None:
            user.watchlists = []
        
        if ticker not in user.watchlists:
            user.watchlists.append(ticker)
            logger.info(f"Added {ticker} to watchlist for user: {user_id}")
        
        return True
    
    def remove_from_watchlist(self, user_id: str, ticker: str) -> bool:
        """Remove ticker from user's watchlist"""
        if user_id not in self.users:
            return False
        
        user = self.users[user_id]
        if user.watchlists and ticker in user.watchlists:
            user.watchlists.remove(ticker)
            logger.info(f"Removed {ticker} from watchlist for user: {user_id}")
        
        return True
    
    def get_user_watchlist(self, user_id: str) -> List[str]:
        """Get user's watchlist"""
        if user_id not in self.users:
            return []
        
        user = self.users[user_id]
        return user.watchlists or []
    
    def create_portfolio(self, user_id: str, portfolio_name: str) -> bool:
        """Create a new portfolio for user"""
        if user_id not in self.users:
            return False
        
        user = self.users[user_id]
        if user.portfolios is None:
            user.portfolios = []
        
        portfolio_id = f"portfolio_{len(user.portfolios) + 1}"
        user.portfolios.append(portfolio_id)
        
        logger.info(f"Created portfolio {portfolio_name} ({portfolio_id}) for user: {user_id}")
        return True
    
    def get_user_portfolios(self, user_id: str) -> List[str]:
        """Get user's portfolios"""
        if user_id not in self.users:
            return []
        
        user = self.users[user_id]
        return user.portfolios or []

class AuthManager:
    """Authentication and authorization manager"""
    
    def __init__(self, user_manager: UserManager):
        self.user_manager = user_manager
        self.active_tokens: Dict[str, str] = {}  # token -> user_id
    
    def create_access_token(self, user_id: str) -> str:
        """Create access token for user"""
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        to_encode = {"sub": user_id, "exp": expire}
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        
        self.active_tokens[encoded_jwt] = user_id
        logger.info(f"Created access token for user: {user_id}")
        return encoded_jwt
    
    def verify_token(self, token: str) -> Optional[str]:
        """Verify token and return user_id"""
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            user_id: str = payload.get("sub")
            if user_id is None:
                return None
            
            # Check if token is still active
            if token not in self.active_tokens:
                return None
            
            return user_id
        except JWTError:
            return None
    
    def revoke_token(self, token: str) -> bool:
        """Revoke access token"""
        if token in self.active_tokens:
            del self.active_tokens[token]
            logger.info(f"Revoked access token")
            return True
        return False
    
    def revoke_all_user_tokens(self, user_id: str) -> int:
        """Revoke all tokens for a user"""
        revoked_count = 0
        tokens_to_revoke = [token for token, uid in self.active_tokens.items() if uid == user_id]
        
        for token in tokens_to_revoke:
            del self.active_tokens[token]
            revoked_count += 1
        
        logger.info(f"Revoked {revoked_count} tokens for user: {user_id}")
        return revoked_count

# Global instances
_user_manager = UserManager()
_auth_manager = AuthManager(_user_manager)

def get_user_manager() -> UserManager:
    """Get global user manager instance"""
    return _user_manager

def get_auth_manager() -> AuthManager:
    """Get global auth manager instance"""
    return _auth_manager

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> User:
    """Get current authenticated user"""
    token = credentials.credentials
    user_id = _auth_manager.verify_token(token)
    
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user = _user_manager.get_user_by_id(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user

async def get_current_user_optional(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> Optional[User]:
    """Get current user if authenticated, None otherwise"""
    if not credentials:
        return None
    
    try:
        return await get_current_user(credentials)
    except HTTPException:
        return None

# User registration and login functions
def register_user(email: str, username: str, full_name: str, password: str) -> Dict[str, Any]:
    """Register a new user"""
    try:
        user = _user_manager.create_user(email, username, full_name, password)
        access_token = _auth_manager.create_access_token(user.id)
        
        return {
            "user": {
                "id": user.id,
                "email": user.email,
                "username": user.username,
                "full_name": user.full_name,
                "created_at": user.created_at.isoformat(),
                "is_premium": user.is_premium
            },
            "access_token": access_token,
            "token_type": "bearer"
        }
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error registering user: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

def login_user(email_or_username: str, password: str) -> Dict[str, Any]:
    """Login user"""
    user = _user_manager.authenticate_user(email_or_username, password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email/username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = _auth_manager.create_access_token(user.id)
    
    return {
        "user": {
            "id": user.id,
            "email": user.email,
            "username": user.username,
            "full_name": user.full_name,
            "last_login": user.last_login.isoformat() if user.last_login else None,
            "is_premium": user.is_premium
        },
        "access_token": access_token,
        "token_type": "bearer"
    }

def logout_user(token: str) -> bool:
    """Logout user by revoking token"""
    return _auth_manager.revoke_token(token)
