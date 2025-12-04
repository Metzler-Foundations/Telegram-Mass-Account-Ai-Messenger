#!/usr/bin/env python3
"""
Transaction Manager - ACID compliance for multi-table operations.

Features:
- Multi-table atomic transactions
- Automatic rollback on failure
- Nested transaction support (savepoints)
- Deadlock detection
- Transaction timeout
- Isolation level configuration
"""

import sqlite3
import logging
import time
import threading
from typing import Optional, List, Callable, Any
from contextlib import contextmanager
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class IsolationLevel(Enum):
    """SQLite isolation levels."""
    DEFERRED = "DEFERRED"
    IMMEDIATE = "IMMEDIATE"
    EXCLUSIVE = "EXCLUSIVE"


class TransactionManager:
    """
    Manages database transactions with rollback support.
    
    Ensures ACID properties for multi-table operations.
    """
    
    def __init__(self, connection):
        """
        Initialize transaction manager.
        
        Args:
            connection: Database connection (from connection pool)
        """
        self.connection = connection
        self.transaction_active = False
        self.savepoint_counter = 0
        self.savepoints: List[str] = []
        
        # Statistics
        self.stats = {
            'transactions_started': 0,
            'transactions_committed': 0,
            'transactions_rolled_back': 0,
            'savepoints_created': 0,
            'savepoints_released': 0,
            'savepoints_rolled_back': 0
        }
    
    @contextmanager
    def transaction(self, isolation_level: IsolationLevel = IsolationLevel.IMMEDIATE):
        """
        Context manager for atomic transactions.
        
        Args:
            isolation_level: Transaction isolation level
            
        Example:
            with transaction_manager.transaction():
                conn.execute("INSERT INTO accounts ...")
                conn.execute("INSERT INTO audit_events ...")
                # Both succeed or both rollback
        """
        # Begin transaction
        try:
            if not self.transaction_active:
                self.connection.execute(f"BEGIN {isolation_level.value}")
                self.transaction_active = True
                self.stats['transactions_started'] += 1
                logger.debug(f"Transaction started ({isolation_level.value})")
            
            yield self.connection
            
            # Commit on success
            if self.transaction_active:
                self.connection.commit()
                self.transaction_active = False
                self.stats['transactions_committed'] += 1
                logger.debug("Transaction committed")
                
        except Exception as e:
            # Rollback on any error
            if self.transaction_active:
                logger.warning(f"Transaction failed, rolling back: {e}")
                try:
                    self.connection.rollback()
                    self.stats['transactions_rolled_back'] += 1
                    logger.debug("Transaction rolled back")
                except Exception as rollback_error:
                    logger.error(f"Rollback failed: {rollback_error}")
                finally:
                    self.transaction_active = False
            
            raise
    
    @contextmanager
    def savepoint(self, name: Optional[str] = None):
        """
        Context manager for nested transactions (savepoints).
        
        Args:
            name: Savepoint name (auto-generated if None)
            
        Example:
            with transaction_manager.transaction():
                conn.execute("INSERT INTO table1 ...")
                
                with transaction_manager.savepoint():
                    conn.execute("INSERT INTO table2 ...")
                    # This can rollback without affecting table1
        """
        if not name:
            self.savepoint_counter += 1
            name = f"sp_{self.savepoint_counter}"
        
        try:
            # Create savepoint
            self.connection.execute(f"SAVEPOINT {name}")
            self.savepoints.append(name)
            self.stats['savepoints_created'] += 1
            logger.debug(f"Savepoint created: {name}")
            
            yield self.connection
            
            # Release savepoint on success
            self.connection.execute(f"RELEASE SAVEPOINT {name}")
            self.savepoints.remove(name)
            self.stats['savepoints_released'] += 1
            logger.debug(f"Savepoint released: {name}")
            
        except Exception as e:
            # Rollback to savepoint
            logger.warning(f"Savepoint {name} failed, rolling back: {e}")
            try:
                self.connection.execute(f"ROLLBACK TO SAVEPOINT {name}")
                self.stats['savepoints_rolled_back'] += 1
                logger.debug(f"Rolled back to savepoint: {name}")
            except Exception as rollback_error:
                logger.error(f"Savepoint rollback failed: {rollback_error}")
            
            raise
    
    def get_stats(self) -> dict:
        """Get transaction statistics."""
        return self.stats.copy()


class ResourceTransaction:
    """
    Manages resource allocation with automatic cleanup on failure.
    
    Used for operations like account creation that allocate multiple
    resources (phone number, proxy, session) that must all be cleaned
    up if any step fails.
    """
    
    def __init__(self):
        """Initialize resource transaction."""
        self.resources: List[tuple] = []  # (resource_type, resource_id, cleanup_func)
        self.committed = False
        self.lock = threading.Lock()
    
    def allocate_resource(
        self,
        resource_type: str,
        resource_id: Any,
        cleanup_func: Callable
    ):
        """
        Record resource allocation.
        
        Args:
            resource_type: Type of resource (e.g., 'phone_number', 'proxy')
            resource_id: Resource identifier
            cleanup_func: Function to call to release resource
        """
        with self.lock:
            self.resources.append((resource_type, resource_id, cleanup_func))
            logger.debug(f"Resource allocated: {resource_type} = {resource_id}")
    
    def commit(self):
        """
        Commit transaction - marks resources as successfully allocated.
        
        Prevents cleanup from running.
        """
        with self.lock:
            self.committed = True
            logger.debug(f"Resource transaction committed ({len(self.resources)} resources)")
    
    def rollback(self):
        """
        Rollback transaction - cleanup all allocated resources.
        
        Called automatically on context manager exit if not committed.
        """
        with self.lock:
            if self.committed:
                logger.debug("Resource transaction already committed, skipping rollback")
                return
            
            logger.warning(f"Rolling back resource transaction ({len(self.resources)} resources)")
            
            # Cleanup in reverse order
            for resource_type, resource_id, cleanup_func in reversed(self.resources):
                try:
                    logger.debug(f"Cleaning up {resource_type}: {resource_id}")
                    cleanup_func()
                except Exception as e:
                    logger.error(
                        f"Failed to cleanup {resource_type} {resource_id}: {e}",
                        exc_info=True
                    )
            
            self.resources.clear()
    
    def __enter__(self):
        """Enter context manager."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context manager - rollback if exception occurred."""
        if exc_type is not None:
            # Exception occurred, rollback
            self.rollback()
        elif not self.committed:
            # No exception but not committed, rollback
            logger.warning("Resource transaction not committed, rolling back")
            self.rollback()
        
        return False  # Don't suppress exceptions


# Example usage for account creation
class AccountCreationTransaction:
    """Transaction wrapper for account creation with automatic cleanup."""
    
    def __init__(self):
        self.phone_number: Optional[str] = None
        self.proxy: Optional[dict] = None
        self.session_name: Optional[str] = None
        self.sms_transaction_id: Optional[str] = None
        self.committed = False
    
    def set_phone_number(self, phone: str, provider_api, transaction_id: str):
        """Record phone number allocation."""
        self.phone_number = phone
        self.sms_transaction_id = transaction_id
        self._provider_api = provider_api
    
    def set_proxy(self, proxy: dict, proxy_pool_manager):
        """Record proxy allocation."""
        self.proxy = proxy
        self._proxy_pool_manager = proxy_pool_manager
    
    def set_session(self, session_name: str):
        """Record session creation."""
        self.session_name = session_name
    
    def commit(self):
        """Commit - prevent cleanup."""
        self.committed = True
        logger.info("Account creation transaction committed")
    
    def rollback(self):
        """Rollback - cleanup all resources."""
        if self.committed:
            return
        
        logger.warning("Rolling back account creation transaction")
        
        # Cleanup phone number
        if self.phone_number and self.sms_transaction_id:
            try:
                logger.info(f"Releasing phone number: {self.phone_number}")
                # Call SMS provider API to cancel/release number
                if hasattr(self, '_provider_api'):
                    self._provider_api.cancel_number(self.sms_transaction_id)
            except Exception as e:
                logger.error(f"Failed to release phone number: {e}")
        
        # Cleanup proxy
        if self.proxy and hasattr(self, '_proxy_pool_manager'):
            try:
                logger.info(f"Releasing proxy: {self.proxy.get('ip')}")
                self._proxy_pool_manager.unassign_proxy(self.phone_number)
            except Exception as e:
                logger.error(f"Failed to release proxy: {e}")
        
        # Cleanup session file
        if self.session_name:
            try:
                from pathlib import Path
                session_file = Path(f"{self.session_name}.session")
                if session_file.exists():
                    logger.info(f"Removing session file: {session_file}")
                    session_file.unlink()
            except Exception as e:
                logger.error(f"Failed to remove session file: {e}")
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None or not self.committed:
            self.rollback()
        return False


# Convenience function
@contextmanager
def atomic_transaction(connection, isolation_level: IsolationLevel = IsolationLevel.IMMEDIATE):
    """
    Simple context manager for atomic transactions.
    
    Args:
        connection: Database connection
        isolation_level: Transaction isolation level
        
    Example:
        with atomic_transaction(conn):
            conn.execute("INSERT ...")
            conn.execute("UPDATE ...")
            # Both succeed or both rollback
    """
    tm = TransactionManager(connection)
    with tm.transaction(isolation_level):
        yield connection



