"""
Session Management and Cleanup System

This module provides comprehensive session management for HTTP clients,
database connections, and other resources to prevent memory leaks.
"""

import asyncio
import logging
import weakref
from typing import Dict, List, Optional, Any
from contextlib import asynccontextmanager
import aiohttp
import threading
import time

logger = logging.getLogger(__name__)


class SessionManager:
    """
    Centralized session management for all HTTP clients and resources
    """
    
    def __init__(self):
        self.sessions: Dict[str, Any] = {}
        self.cleanup_callbacks: List[callable] = []
        self._lock = threading.Lock()
        self._cleanup_thread: Optional[threading.Thread] = None
        self._shutdown_event = threading.Event()
        
        # Start cleanup thread
        self._start_cleanup_thread()
        
        logger.info("SessionManager initialized")
    
    def register_session(self, name: str, session: Any, cleanup_func: Optional[callable] = None):
        """Register a session for management"""
        with self._lock:
            self.sessions[name] = session
            if cleanup_func:
                self.cleanup_callbacks.append(cleanup_func)
            
            logger.debug(f"Registered session: {name}")
    
    def get_session(self, name: str) -> Optional[Any]:
        """Get a registered session"""
        with self._lock:
            return self.sessions.get(name)
    
    def unregister_session(self, name: str):
        """Unregister a session"""
        with self._lock:
            if name in self.sessions:
                del self.sessions[name]
                logger.debug(f"Unregistered session: {name}")
    
    async def cleanup_session(self, name: str):
        """Cleanup a specific session"""
        session = self.get_session(name)
        if session:
            try:
                if hasattr(session, 'close') and not session.closed:
                    await session.close()
                    logger.info(f"Closed session: {name}")
            except Exception as e:
                logger.warning(f"Error closing session {name}: {e}")
            finally:
                self.unregister_session(name)
    
    async def cleanup_all_sessions(self):
        """Cleanup all registered sessions"""
        logger.info("Starting cleanup of all sessions")
        
        # Get all session names to avoid modification during iteration
        session_names = list(self.sessions.keys())
        
        # Cleanup sessions in parallel
        cleanup_tasks = []
        for name in session_names:
            cleanup_tasks.append(self.cleanup_session(name))
        
        if cleanup_tasks:
            await asyncio.gather(*cleanup_tasks, return_exceptions=True)
        
        # Run cleanup callbacks
        for callback in self.cleanup_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback()
                else:
                    callback()
            except Exception as e:
                logger.warning(f"Error in cleanup callback: {e}")
        
        logger.info("Completed cleanup of all sessions")
    
    def _start_cleanup_thread(self):
        """Start background cleanup thread"""
        self._cleanup_thread = threading.Thread(
            target=self._cleanup_loop,
            daemon=True,
            name="SessionCleanupThread"
        )
        self._cleanup_thread.start()
    
    def _cleanup_loop(self):
        """Background cleanup loop"""
        while not self._shutdown_event.is_set():
            try:
                # Check for stale sessions every 30 seconds
                self._shutdown_event.wait(30)
                
                if not self._shutdown_event.is_set():
                    self._cleanup_stale_sessions()
                    
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")
    
    def _cleanup_stale_sessions(self):
        """Cleanup stale sessions synchronously"""
        with self._lock:
            stale_sessions = []
            
            for name, session in self.sessions.items():
                try:
                    # Check if session is stale (closed or has errors)
                    if hasattr(session, 'closed') and session.closed:
                        stale_sessions.append(name)
                    elif hasattr(session, '_connector') and session._connector.closed:
                        stale_sessions.append(name)
                except Exception:
                    # If we can't check the session state, consider it stale
                    stale_sessions.append(name)
            
            # Remove stale sessions
            for name in stale_sessions:
                logger.info(f"Removing stale session: {name}")
                del self.sessions[name]
    
    def shutdown(self):
        """Shutdown the session manager"""
        logger.info("Shutting down SessionManager")
        self._shutdown_event.set()
        
        if self._cleanup_thread:
            self._cleanup_thread.join(timeout=5.0)
        
        # Final cleanup
        asyncio.create_task(self.cleanup_all_sessions())


# Global session manager instance
_session_manager: Optional[SessionManager] = None


def get_session_manager() -> SessionManager:
    """Get the global session manager instance"""
    global _session_manager
    
    if _session_manager is None:
        _session_manager = SessionManager()
    
    return _session_manager


@asynccontextmanager
async def managed_session(name: str, session_factory, *args, **kwargs):
    """
    Context manager for creating and managing sessions
    """
    session_manager = get_session_manager()
    
    # Create session
    session = session_factory(*args, **kwargs)
    
    # Register session
    session_manager.register_session(name, session)
    
    try:
        yield session
    finally:
        # Cleanup session
        await session_manager.cleanup_session(name)


class HTTPClientManager:
    """
    Specialized manager for HTTP clients with connection pooling
    """
    
    def __init__(self):
        self.session_manager = get_session_manager()
        self.default_timeout = aiohttp.ClientTimeout(total=30)
        self.default_headers = {
            'User-Agent': 'EquiSense AI Research Tool (contact@equisense.ai)',
            'Accept': 'application/json',
            'Accept-Encoding': 'gzip, deflate'
        }
    
    async def create_session(
        self, 
        name: str, 
        timeout: Optional[aiohttp.ClientTimeout] = None,
        headers: Optional[Dict[str, str]] = None,
        connector: Optional[aiohttp.BaseConnector] = None
    ) -> aiohttp.ClientSession:
        """Create and register an HTTP session"""
        
        # Merge headers
        session_headers = self.default_headers.copy()
        if headers:
            session_headers.update(headers)
        
        # Create session
        session = aiohttp.ClientSession(
            timeout=timeout or self.default_timeout,
            headers=session_headers,
            connector=connector,
            raise_for_status=False  # Handle errors manually
        )
        
        # Register with session manager
        self.session_manager.register_session(name, session)
        
        logger.info(f"Created HTTP session: {name}")
        return session
    
    async def get_or_create_session(
        self, 
        name: str, 
        **kwargs
    ) -> aiohttp.ClientSession:
        """Get existing session or create new one"""
        existing_session = self.session_manager.get_session(name)
        
        if existing_session and not existing_session.closed:
            return existing_session
        
        return await self.create_session(name, **kwargs)
    
    async def cleanup_all_http_sessions(self):
        """Cleanup all HTTP sessions"""
        await self.session_manager.cleanup_all_sessions()


# Global HTTP client manager
_http_client_manager: Optional[HTTPClientManager] = None


def get_http_client_manager() -> HTTPClientManager:
    """Get the global HTTP client manager"""
    global _http_client_manager
    
    if _http_client_manager is None:
        _http_client_manager = HTTPClientManager()
    
    return _http_client_manager


# Convenience functions
async def create_managed_session(name: str, **kwargs) -> aiohttp.ClientSession:
    """Create a managed HTTP session"""
    manager = get_http_client_manager()
    return await manager.create_session(name, **kwargs)


async def cleanup_all_sessions():
    """Cleanup all managed sessions"""
    session_manager = get_session_manager()
    await session_manager.cleanup_all_sessions()


async def shutdown_session_manager():
    """Shutdown the session manager"""
    session_manager = get_session_manager()
    session_manager.shutdown()


# Auto-cleanup on module unload
import atexit
def cleanup_on_exit():
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.create_task(shutdown_session_manager())
    except RuntimeError:
        # No event loop running, skip cleanup
        pass

atexit.register(cleanup_on_exit)
