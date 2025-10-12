"""
Security and compliance system for EquiSense AI
Implements authentication, authorization, audit logging, and data protection
"""

import asyncio
import logging
import hashlib
import secrets
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field
from enum import Enum
try:
    import jwt
    JWT_AVAILABLE = True
except ImportError:
    JWT_AVAILABLE = False
    logging.warning("PyJWT not available. JWT functionality will be disabled.")

try:
    from passlib.context import CryptContext
    from passlib.hash import bcrypt
    PASSWORD_AVAILABLE = True
except ImportError:
    PASSWORD_AVAILABLE = False
    logging.warning("Passlib not available. Password functionality will be disabled.")

try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    import base64
    ENCRYPTION_AVAILABLE = True
except ImportError:
    ENCRYPTION_AVAILABLE = False
    logging.warning("Cryptography library not available. Encryption will be disabled.")

logger = logging.getLogger(__name__)


class UserRole(Enum):
    """User roles for RBAC"""
    ADMIN = "admin"
    ANALYST = "analyst"
    VIEWER = "viewer"
    API_USER = "api_user"


class Permission(Enum):
    """System permissions"""
    READ_ANALYSIS = "read_analysis"
    WRITE_ANALYSIS = "write_analysis"
    READ_PORTFOLIO = "read_portfolio"
    WRITE_PORTFOLIO = "write_portfolio"
    READ_REPORTS = "read_reports"
    WRITE_REPORTS = "write_reports"
    MANAGE_USERS = "manage_users"
    SYSTEM_ADMIN = "system_admin"
    API_ACCESS = "api_access"


@dataclass
class User:
    """User model"""
    user_id: str
    username: str
    email: str
    password_hash: str
    roles: List[UserRole] = field(default_factory=list)
    permissions: List[Permission] = field(default_factory=list)
    is_active: bool = True
    is_verified: bool = False
    created_at: datetime = field(default_factory=datetime.now)
    last_login: Optional[datetime] = None
    failed_login_attempts: int = 0
    locked_until: Optional[datetime] = None


@dataclass
class AuditLog:
    """Audit log entry"""
    log_id: str
    user_id: Optional[str]
    action: str
    resource: str
    resource_id: Optional[str]
    details: Dict[str, Any]
    ip_address: Optional[str]
    user_agent: Optional[str]
    timestamp: datetime = field(default_factory=datetime.now)
    success: bool = True


class PasswordManager:
    """Password management utilities"""
    
    def __init__(self):
        if not PASSWORD_AVAILABLE:
            logger.warning("Password functionality not available")
        self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto") if PASSWORD_AVAILABLE else None
        
    def hash_password(self, password: str) -> str:
        """Hash a password"""
        if not self.pwd_context:
            logger.warning("Password hashing not available")
            return password  # Fallback
        return self.pwd_context.hash(password)
        
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash"""
        if not self.pwd_context:
            logger.warning("Password verification not available")
            return plain_password == hashed_password  # Fallback
        return self.pwd_context.verify(plain_password, hashed_password)
        
    def generate_password(self, length: int = 16) -> str:
        """Generate a secure random password"""
        alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*"
        return ''.join(secrets.choice(alphabet) for _ in range(length))


class EncryptionManager:
    """Data encryption utilities"""
    
    def __init__(self, master_key: Optional[str] = None):
        self.master_key = master_key or self._generate_master_key()
        self.fernet = self._create_fernet()
        
    def _generate_master_key(self) -> str:
        """Generate a master encryption key"""
        if ENCRYPTION_AVAILABLE:
            return Fernet.generate_key().decode()
        else:
            # Fallback to a simple random key
            import secrets
            return secrets.token_urlsafe(32)
        
    def _create_fernet(self) -> Optional[Any]:
        """Create Fernet encryption instance"""
        if not ENCRYPTION_AVAILABLE:
            return None
            
        try:
            # Derive key from master key
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=b'equisense_salt',  # In production, use random salt
                iterations=100000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(self.master_key.encode()))
            return Fernet(key)
        except Exception as e:
            logger.error(f"Failed to create Fernet instance: {e}")
            return None
            
    def encrypt_data(self, data: str) -> str:
        """Encrypt sensitive data"""
        if not self.fernet:
            logger.warning("Encryption not available, returning original data")
            return data
            
        try:
            encrypted_data = self.fernet.encrypt(data.encode())
            return base64.urlsafe_b64encode(encrypted_data).decode()
        except Exception as e:
            logger.error(f"Failed to encrypt data: {e}")
            return data
            
    def decrypt_data(self, encrypted_data: str) -> str:
        """Decrypt sensitive data"""
        if not self.fernet:
            logger.warning("Decryption not available, returning original data")
            return encrypted_data
            
        try:
            decoded_data = base64.urlsafe_b64decode(encrypted_data.encode())
            decrypted_data = self.fernet.decrypt(decoded_data)
            return decrypted_data.decode()
        except Exception as e:
            logger.error(f"Failed to decrypt data: {e}")
            return encrypted_data


class JWTManager:
    """JWT token management"""
    
    def __init__(self, secret_key: str, algorithm: str = "HS256"):
        if not JWT_AVAILABLE:
            logger.warning("JWT functionality not available")
        self.secret_key = secret_key
        self.algorithm = algorithm
        
    def create_access_token(self, user_id: str, roles: List[UserRole], expires_delta: Optional[timedelta] = None) -> str:
        """Create JWT access token"""
        if not JWT_AVAILABLE:
            logger.warning("JWT token creation not available")
            return f"mock_token_{user_id}_{datetime.now().timestamp()}"
            
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(hours=24)
            
        to_encode = {
            "sub": user_id,
            "roles": [role.value for role in roles],
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "access"
        }
        
        return jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        
    def create_refresh_token(self, user_id: str, expires_delta: Optional[timedelta] = None) -> str:
        """Create JWT refresh token"""
        if not JWT_AVAILABLE:
            logger.warning("JWT refresh token creation not available")
            return f"mock_refresh_{user_id}_{datetime.now().timestamp()}"
            
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(days=30)
            
        to_encode = {
            "sub": user_id,
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "refresh"
        }
        
        return jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        
    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify JWT token"""
        if not JWT_AVAILABLE:
            logger.warning("JWT token verification not available")
            return {"sub": "mock_user", "type": "access"}  # Mock response
            
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except jwt.ExpiredSignatureError:
            logger.warning("Token has expired")
            return None
        except jwt.InvalidTokenError:
            logger.warning("Invalid token")
            return None


class RBACManager:
    """Role-Based Access Control manager"""
    
    def __init__(self):
        self.role_permissions = {
            UserRole.ADMIN: [
                Permission.READ_ANALYSIS,
                Permission.WRITE_ANALYSIS,
                Permission.READ_PORTFOLIO,
                Permission.WRITE_PORTFOLIO,
                Permission.READ_REPORTS,
                Permission.WRITE_REPORTS,
                Permission.MANAGE_USERS,
                Permission.SYSTEM_ADMIN,
                Permission.API_ACCESS
            ],
            UserRole.ANALYST: [
                Permission.READ_ANALYSIS,
                Permission.WRITE_ANALYSIS,
                Permission.READ_PORTFOLIO,
                Permission.WRITE_PORTFOLIO,
                Permission.READ_REPORTS,
                Permission.WRITE_REPORTS,
                Permission.API_ACCESS
            ],
            UserRole.VIEWER: [
                Permission.READ_ANALYSIS,
                Permission.READ_PORTFOLIO,
                Permission.READ_REPORTS
            ],
            UserRole.API_USER: [
                Permission.API_ACCESS,
                Permission.READ_ANALYSIS
            ]
        }
        
    def has_permission(self, user: User, permission: Permission) -> bool:
        """Check if user has specific permission"""
        # Check direct permissions
        if permission in user.permissions:
            return True
            
        # Check role-based permissions
        for role in user.roles:
            if permission in self.role_permissions.get(role, []):
                return True
                
        return False
        
    def get_user_permissions(self, user: User) -> List[Permission]:
        """Get all permissions for a user"""
        permissions = set(user.permissions)
        
        for role in user.roles:
            permissions.update(self.role_permissions.get(role, []))
            
        return list(permissions)


class AuditLogger:
    """Audit logging system"""
    
    def __init__(self):
        self.logs: List[AuditLog] = []
        
    def log_action(
        self,
        user_id: Optional[str],
        action: str,
        resource: str,
        resource_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        success: bool = True
    ) -> None:
        """Log an audit event"""
        log_id = f"audit_{datetime.now().timestamp()}_{secrets.token_hex(4)}"
        
        audit_log = AuditLog(
            log_id=log_id,
            user_id=user_id,
            action=action,
            resource=resource,
            resource_id=resource_id,
            details=details or {},
            ip_address=ip_address,
            user_agent=user_agent,
            success=success
        )
        
        self.logs.append(audit_log)
        logger.info(f"Audit log: {action} on {resource} by {user_id} - {'SUCCESS' if success else 'FAILED'}")
        
    def get_user_logs(self, user_id: str, limit: int = 100) -> List[AuditLog]:
        """Get audit logs for a specific user"""
        user_logs = [log for log in self.logs if log.user_id == user_id]
        return sorted(user_logs, key=lambda x: x.timestamp, reverse=True)[:limit]
        
    def get_resource_logs(self, resource: str, resource_id: Optional[str] = None, limit: int = 100) -> List[AuditLog]:
        """Get audit logs for a specific resource"""
        resource_logs = [
            log for log in self.logs 
            if log.resource == resource and (resource_id is None or log.resource_id == resource_id)
        ]
        return sorted(resource_logs, key=lambda x: x.timestamp, reverse=True)[:limit]
        
    def export_logs(self, start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
        """Export audit logs for a date range"""
        filtered_logs = [
            log for log in self.logs 
            if start_date <= log.timestamp <= end_date
        ]
        
        return [
            {
                "log_id": log.log_id,
                "user_id": log.user_id,
                "action": log.action,
                "resource": log.resource,
                "resource_id": log.resource_id,
                "details": log.details,
                "ip_address": log.ip_address,
                "user_agent": log.user_agent,
                "timestamp": log.timestamp.isoformat(),
                "success": log.success
            }
            for log in filtered_logs
        ]


class SecurityManager:
    """Main security manager"""
    
    def __init__(self, jwt_secret: str, encryption_key: Optional[str] = None):
        self.password_manager = PasswordManager()
        self.encryption_manager = EncryptionManager(encryption_key)
        self.jwt_manager = JWTManager(jwt_secret)
        self.rbac_manager = RBACManager()
        self.audit_logger = AuditLogger()
        self.users: Dict[str, User] = {}
        
    def create_user(
        self,
        username: str,
        email: str,
        password: str,
        roles: List[UserRole] = None,
        permissions: List[Permission] = None
    ) -> User:
        """Create a new user"""
        user_id = f"user_{secrets.token_hex(8)}"
        password_hash = self.password_manager.hash_password(password)
        
        user = User(
            user_id=user_id,
            username=username,
            email=email,
            password_hash=password_hash,
            roles=roles or [UserRole.VIEWER],
            permissions=permissions or []
        )
        
        self.users[user_id] = user
        
        self.audit_logger.log_action(
            user_id=None,
            action="user_created",
            resource="user",
            resource_id=user_id,
            details={"username": username, "email": email, "roles": [r.value for r in user.roles]}
        )
        
        return user
        
    def authenticate_user(self, username: str, password: str, ip_address: Optional[str] = None) -> Optional[User]:
        """Authenticate a user"""
        # Find user by username or email
        user = None
        for u in self.users.values():
            if u.username == username or u.email == username:
                user = u
                break
                
        if not user:
            self.audit_logger.log_action(
                user_id=None,
                action="login_attempt",
                resource="user",
                details={"username": username, "reason": "user_not_found"},
                ip_address=ip_address,
                success=False
            )
            return None
            
        # Check if account is locked
        if user.locked_until and datetime.now() < user.locked_until:
            self.audit_logger.log_action(
                user_id=user.user_id,
                action="login_attempt",
                resource="user",
                details={"reason": "account_locked"},
                ip_address=ip_address,
                success=False
            )
            return None
            
        # Verify password
        if not self.password_manager.verify_password(password, user.password_hash):
            user.failed_login_attempts += 1
            
            # Lock account after 5 failed attempts
            if user.failed_login_attempts >= 5:
                user.locked_until = datetime.now() + timedelta(minutes=30)
                
            self.audit_logger.log_action(
                user_id=user.user_id,
                action="login_attempt",
                resource="user",
                details={"reason": "invalid_password", "failed_attempts": user.failed_login_attempts},
                ip_address=ip_address,
                success=False
            )
            return None
            
        # Reset failed attempts on successful login
        user.failed_login_attempts = 0
        user.locked_until = None
        user.last_login = datetime.now()
        
        self.audit_logger.log_action(
            user_id=user.user_id,
            action="login_success",
            resource="user",
            ip_address=ip_address,
            success=True
        )
        
        return user
        
    def create_tokens(self, user: User) -> Dict[str, str]:
        """Create access and refresh tokens for user"""
        access_token = self.jwt_manager.create_access_token(
            user.user_id,
            user.roles,
            expires_delta=timedelta(hours=24)
        )
        
        refresh_token = self.jwt_manager.create_refresh_token(
            user.user_id,
            expires_delta=timedelta(days=30)
        )
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer"
        }
        
    def verify_access_token(self, token: str) -> Optional[User]:
        """Verify access token and return user"""
        payload = self.jwt_manager.verify_token(token)
        if not payload or payload.get("type") != "access":
            return None
            
        user_id = payload.get("sub")
        if not user_id or user_id not in self.users:
            return None
            
        return self.users[user_id]
        
    def check_permission(self, user: User, permission: Permission) -> bool:
        """Check if user has permission"""
        has_perm = self.rbac_manager.has_permission(user, permission)
        
        self.audit_logger.log_action(
            user_id=user.user_id,
            action="permission_check",
            resource="permission",
            resource_id=permission.value,
            details={"permission": permission.value, "granted": has_perm},
            success=has_perm
        )
        
        return has_perm
        
    def encrypt_sensitive_data(self, data: str) -> str:
        """Encrypt sensitive data"""
        return self.encryption_manager.encrypt_data(data)
        
    def decrypt_sensitive_data(self, encrypted_data: str) -> str:
        """Decrypt sensitive data"""
        return self.encryption_manager.decrypt_data(encrypted_data)
        
    def get_audit_logs(self, user_id: Optional[str] = None, resource: Optional[str] = None) -> List[AuditLog]:
        """Get audit logs"""
        if user_id:
            return self.audit_logger.get_user_logs(user_id)
        elif resource:
            return self.audit_logger.get_resource_logs(resource)
        else:
            return sorted(self.audit_logger.logs, key=lambda x: x.timestamp, reverse=True)[:100]


# Global security manager instance
_security_manager = None

def get_security_manager() -> SecurityManager:
    """Get the global security manager instance"""
    global _security_manager
    if _security_manager is None:
        # In production, use environment variables for secrets
        jwt_secret = "equisense_jwt_secret_key_change_in_production"
        encryption_key = "equisense_encryption_key_change_in_production"
        _security_manager = SecurityManager(jwt_secret, encryption_key)
    return _security_manager
