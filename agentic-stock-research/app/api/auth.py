"""
Security and authentication API endpoints
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
import secrets

from app.security.auth import (
    get_security_manager, SecurityManager, User, UserRole, Permission,
    AuditLog
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])
security = HTTPBearer()


# Pydantic models for API requests/responses
class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: str = Field(..., pattern=r'^[^@]+@[^@]+\.[^@]+$')
    password: str = Field(..., min_length=8)
    roles: List[str] = Field(default_factory=lambda: ["viewer"])


class UserLogin(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = 86400  # 24 hours


class UserResponse(BaseModel):
    user_id: str
    username: str
    email: str
    roles: List[str]
    permissions: List[str]
    is_active: bool
    is_verified: bool
    created_at: datetime
    last_login: Optional[datetime]


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8)


class AuditLogResponse(BaseModel):
    log_id: str
    user_id: Optional[str]
    action: str
    resource: str
    resource_id: Optional[str]
    details: Dict[str, Any]
    ip_address: Optional[str]
    user_agent: Optional[str]
    timestamp: datetime
    success: bool


# Dependency to get current user
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    request: Request = None
) -> User:
    """Get current authenticated user"""
    security_manager = get_security_manager()
    
    user = security_manager.verify_access_token(credentials.credentials)
    if not user:
        security_manager.audit_logger.log_action(
            user_id=None,
            action="token_verification_failed",
            resource="auth",
            ip_address=request.client.host if request else None,
            user_agent=request.headers.get("user-agent") if request else None,
            success=False
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is disabled"
        )
    
    return user


# Dependency to check permissions
def require_permission(permission: Permission):
    """Decorator to require specific permission"""
    def permission_checker(current_user: User = Depends(get_current_user)):
        security_manager = get_security_manager()
        if not security_manager.check_permission(current_user, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {permission.value}"
            )
        return current_user
    return permission_checker


@router.get("/health")
async def health_check():
    """Health check for security system"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "services": {
            "authentication": "active",
            "authorization": "active",
            "audit_logging": "active",
            "encryption": "active"
        }
    }


@router.post("/register", response_model=UserResponse)
async def register_user(user_data: UserCreate, request: Request):
    """Register a new user"""
    try:
        security_manager = get_security_manager()
        
        # Check if username or email already exists
        for user in security_manager.users.values():
            if user.username == user_data.username:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Username already exists"
                )
            if user.email == user_data.email:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already exists"
                )
        
        # Convert string roles to UserRole enum
        roles = []
        for role_str in user_data.roles:
            try:
                roles.append(UserRole(role_str))
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid role: {role_str}"
                )
        
        # Create user
        user = security_manager.create_user(
            username=user_data.username,
            email=user_data.email,
            password=user_data.password,
            roles=roles
        )
        
        security_manager.audit_logger.log_action(
            user_id=user.user_id,
            action="user_registered",
            resource="user",
            resource_id=user.user_id,
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent"),
            success=True
        )
        
        return UserResponse(
            user_id=user.user_id,
            username=user.username,
            email=user.email,
            roles=[role.value for role in user.roles],
            permissions=[perm.value for perm in security_manager.rbac_manager.get_user_permissions(user)],
            is_active=user.is_active,
            is_verified=user.is_verified,
            created_at=user.created_at,
            last_login=user.last_login
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error registering user: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/login", response_model=TokenResponse)
async def login_user(login_data: UserLogin, request: Request):
    """Authenticate user and return tokens"""
    try:
        security_manager = get_security_manager()
        
        user = security_manager.authenticate_user(
            login_data.username,
            login_data.password,
            ip_address=request.client.host
        )
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password"
            )
        
        # Create tokens
        tokens = security_manager.create_tokens(user)
        
        return TokenResponse(**tokens)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during login: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current user information"""
    security_manager = get_security_manager()
    
    return UserResponse(
        user_id=current_user.user_id,
        username=current_user.username,
        email=current_user.email,
        roles=[role.value for role in current_user.roles],
        permissions=[perm.value for perm in security_manager.rbac_manager.get_user_permissions(current_user)],
        is_active=current_user.is_active,
        is_verified=current_user.is_verified,
        created_at=current_user.created_at,
        last_login=current_user.last_login
    )


@router.post("/change-password")
async def change_password(
    password_data: PasswordChange,
    current_user: User = Depends(get_current_user),
    request: Request = None
):
    """Change user password"""
    try:
        security_manager = get_security_manager()
        
        # Verify current password
        if not security_manager.password_manager.verify_password(
            password_data.current_password,
            current_user.password_hash
        ):
            security_manager.audit_logger.log_action(
                user_id=current_user.user_id,
                action="password_change_failed",
                resource="user",
                resource_id=current_user.user_id,
                details={"reason": "invalid_current_password"},
                ip_address=request.client.host if request else None,
                success=False
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect"
            )
        
        # Update password
        current_user.password_hash = security_manager.password_manager.hash_password(password_data.new_password)
        
        security_manager.audit_logger.log_action(
            user_id=current_user.user_id,
            action="password_changed",
            resource="user",
            resource_id=current_user.user_id,
            ip_address=request.client.host if request else None,
            success=True
        )
        
        return {"message": "Password changed successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error changing password: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/permissions")
async def get_user_permissions(current_user: User = Depends(get_current_user)):
    """Get current user permissions"""
    security_manager = get_security_manager()
    permissions = security_manager.rbac_manager.get_user_permissions(current_user)
    
    return {
        "permissions": [perm.value for perm in permissions],
        "roles": [role.value for role in current_user.roles]
    }


@router.get("/audit-logs", response_model=List[AuditLogResponse])
async def get_audit_logs(
    limit: int = 100,
    user_id: Optional[str] = None,
    resource: Optional[str] = None,
    current_user: User = Depends(require_permission(Permission.SYSTEM_ADMIN))
):
    """Get audit logs (admin only)"""
    try:
        security_manager = get_security_manager()
        
        logs = security_manager.get_audit_logs(user_id, resource)
        logs = logs[:limit]
        
        return [
            AuditLogResponse(
                log_id=log.log_id,
                user_id=log.user_id,
                action=log.action,
                resource=log.resource,
                resource_id=log.resource_id,
                details=log.details,
                ip_address=log.ip_address,
                user_agent=log.user_agent,
                timestamp=log.timestamp,
                success=log.success
            )
            for log in logs
        ]
        
    except Exception as e:
        logger.error(f"Error getting audit logs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/users", response_model=List[UserResponse])
async def list_users(
    current_user: User = Depends(require_permission(Permission.MANAGE_USERS))
):
    """List all users (admin only)"""
    try:
        security_manager = get_security_manager()
        
        users = []
        for user in security_manager.users.values():
            users.append(UserResponse(
                user_id=user.user_id,
                username=user.username,
                email=user.email,
                roles=[role.value for role in user.roles],
                permissions=[perm.value for perm in security_manager.rbac_manager.get_user_permissions(user)],
                is_active=user.is_active,
                is_verified=user.is_verified,
                created_at=user.created_at,
                last_login=user.last_login
            ))
        
        return users
        
    except Exception as e:
        logger.error(f"Error listing users: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/users/{user_id}/activate")
async def activate_user(
    user_id: str,
    current_user: User = Depends(require_permission(Permission.MANAGE_USERS))
):
    """Activate/deactivate a user (admin only)"""
    try:
        security_manager = get_security_manager()
        
        if user_id not in security_manager.users:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        user = security_manager.users[user_id]
        user.is_active = not user.is_active
        
        security_manager.audit_logger.log_action(
            user_id=current_user.user_id,
            action="user_status_changed",
            resource="user",
            resource_id=user_id,
            details={"new_status": "active" if user.is_active else "inactive"},
            success=True
        )
        
        return {"message": f"User {'activated' if user.is_active else 'deactivated'} successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error changing user status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/roles")
async def get_available_roles():
    """Get available user roles"""
    return {
        "roles": [
            {
                "value": role.value,
                "name": role.value.title(),
                "description": f"{role.value.title()} role"
            }
            for role in UserRole
        ]
    }


@router.get("/permissions")
async def get_available_permissions():
    """Get available permissions"""
    return {
        "permissions": [
            {
                "value": perm.value,
                "name": perm.value.replace("_", " ").title(),
                "description": f"Permission to {perm.value.replace('_', ' ')}"
            }
            for perm in Permission
        ]
    }
