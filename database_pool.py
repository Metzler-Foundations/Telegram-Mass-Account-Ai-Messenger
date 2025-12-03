#!/usr/bin/env python3
"""
Advanced Database Connection Pool with prepared statement caching.

Features:
- Thread-safe connection pooling
- Prepared statement caching
- Automatic connection health checks
- Connection lifetime management
- Performance monitoring
"""

import sqlite3
import threading
import logging
import time
from contextlib import contextmanager
from typing import Optional, Dict, Any, List, Tuple
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


@dataclass
class PoolStats:
    """Connection pool statistics."""
    total_connections: int = 0
    active_connections: int = 0
    idle_connections: int = 0
    total_requests: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    avg_wait_time: float = 0.0
    
    def cache_hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self.cache_hits + self.cache_misses
        return (self.cache_hits / total * 100) if total > 0 else 0.0


class PooledConnection:
    """Wrapper for pooled database connection."""
    
    def __init__(self, conn: sqlite3.Connection, pool: 'DatabasePool'):
        self.conn = conn
        self.pool = pool
        self.created_at = time.time()
        self.last_used = time.time()
        self.use_count = 0
        self.in_use = False
        
        # Prepared statement cache per connection
        self.statement_cache: Dict[str, sqlite3.Cursor] = {}
    
    def execute(self, query: str, params: tuple = ()) -> sqlite3.Cursor:
        """Execute query with prepared statement caching."""
        self.last_used = time.time()
        self.use_count += 1
        
        # Check if we should use prepared statements
        if self._should_cache_statement(query):
            return self._execute_cached(query, params)
        else:
            return self.conn.execute(query, params)
    
    def _should_cache_statement(self, query: str) -> bool:
        """Determine if statement should be cached."""
        # Cache SELECT, INSERT, UPDATE, DELETE statements
        query_upper = query.strip().upper()
        return any(query_upper.startswith(cmd) for cmd in ['SELECT', 'INSERT', 'UPDATE', 'DELETE'])
    
    def _execute_cached(self, query: str, params: tuple) -> sqlite3.Cursor:
        """Execute using cached prepared statement."""
        if query in self.statement_cache:
            self.pool.stats.cache_hits += 1
            cursor = self.statement_cache[query]
        else:
            self.pool.stats.cache_misses += 1
            cursor = self.conn.cursor()
            # Cache the statement
            if len(self.statement_cache) < 100:  # Limit cache size
                self.statement_cache[query] = cursor
        
        return cursor.execute(query, params)
    
    def is_healthy(self) -> bool:
        """Check if connection is still healthy."""
        try:
            self.conn.execute("SELECT 1").fetchone()
            return True
        except sqlite3.Error:
            return False
    
    def is_expired(self, max_age: float) -> bool:
        """Check if connection has exceeded max age."""
        return (time.time() - self.created_at) > max_age
    
    def close(self):
        """Close the underlying connection."""
        try:
            self.conn.close()
        except sqlite3.Error as e:
            logger.warning(f"Error closing connection: {e}")


class DatabasePool:
    """
    Advanced database connection pool with prepared statement caching.
    
    Thread-safe connection pooling with:
    - Automatic connection management
    - Statement caching for performance
    - Health checking
    - Connection lifetime limits
    - Performance monitoring
    """
    
    def __init__(
        self,
        db_path: str,
        min_connections: int = 2,
        max_connections: int = 10,
        max_connection_age: float = 3600.0,  # 1 hour
        connection_timeout: float = 5.0
    ):
        """
        Initialize database pool.
        
        Args:
            db_path: Path to SQLite database
            min_connections: Minimum connections to maintain
            max_connections: Maximum connections allowed
            max_connection_age: Max age of connection in seconds
            connection_timeout: Timeout waiting for connection
        """
        self.db_path = db_path
        self.min_connections = min_connections
        self.max_connections = max_connections
        self.max_connection_age = max_connection_age
        self.connection_timeout = connection_timeout
        
        # Connection pools
        self.idle_connections: deque[PooledConnection] = deque()
        self.active_connections: set[PooledConnection] = set()
        
        # Thread safety
        self.lock = threading.RLock()
        self.condition = threading.Condition(self.lock)
        
        # Statistics
        self.stats = PoolStats()
        
        # Initialize minimum connections
        self._initialize_pool()
        
        logger.info(f"Database pool initialized: {db_path} (min={min_connections}, max={max_connections})")
    
    def _initialize_pool(self):
        """Create minimum number of connections."""
        with self.lock:
            for _ in range(self.min_connections):
                try:
                    conn = self._create_connection()
                    if conn:
                        self.idle_connections.append(conn)
                except Exception as e:
                    logger.error(f"Failed to create initial connection: {e}")
    
    def _create_connection(self) -> Optional[PooledConnection]:
        """Create a new database connection."""
        try:
            conn = sqlite3.connect(
                self.db_path,
                check_same_thread=False,  # Allow sharing between threads (safely)
                timeout=self.connection_timeout
            )
            
            # Optimize connection settings
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA cache_size=-64000")  # 64MB cache
            conn.execute("PRAGMA temp_store=MEMORY")
            conn.execute("PRAGMA mmap_size=268435456")  # 256MB mmap
            
            pooled_conn = PooledConnection(conn, self)
            self.stats.total_connections += 1
            
            return pooled_conn
        except sqlite3.Error as e:
            logger.error(f"Failed to create connection: {e}")
            return None
    
    @contextmanager
    def get_connection(self):
        """
        Get a connection from the pool (context manager).
        
        Usage:
            with pool.get_connection() as conn:
                conn.execute("SELECT * FROM table")
        """
        start_time = time.time()
        conn = None
        
        try:
            with self.lock:
                self.stats.total_requests += 1
                
                # Try to get idle connection
                while self.idle_connections:
                    conn = self.idle_connections.popleft()
                    
                    # Check if connection is healthy and not expired
                    if conn.is_expired(self.max_connection_age) or not conn.is_healthy():
                        conn.close()
                        self.stats.total_connections -= 1
                        conn = None
                        continue
                    
                    # Found good connection
                    break
                
                # No idle connections, create new one if under limit
                if conn is None and len(self.active_connections) < self.max_connections:
                    conn = self._create_connection()
                
                # Wait for connection to become available
                if conn is None:
                    wait_time = 0
                    while conn is None and wait_time < self.connection_timeout:
                        self.condition.wait(timeout=0.1)
                        wait_time += 0.1
                        
                        # Try again
                        if self.idle_connections:
                            conn = self.idle_connections.popleft()
                            if not conn.is_healthy():
                                conn.close()
                                conn = None
                    
                    if conn is None:
                        raise sqlite3.OperationalError("Timeout waiting for database connection")
                
                # Mark as active
                conn.in_use = True
                self.active_connections.add(conn)
                self.stats.active_connections = len(self.active_connections)
                self.stats.idle_connections = len(self.idle_connections)
                
                # Update wait time stat
                wait_time = time.time() - start_time
                self.stats.avg_wait_time = (
                    (self.stats.avg_wait_time * (self.stats.total_requests - 1) + wait_time) 
                    / self.stats.total_requests
                )
            
            yield conn
            
        finally:
            # Return connection to pool
            if conn:
                with self.lock:
                    conn.in_use = False
                    self.active_connections.discard(conn)
                    
                    # Return to pool if healthy and not expired
                    if conn.is_healthy() and not conn.is_expired(self.max_connection_age):
                        self.idle_connections.append(conn)
                    else:
                        conn.close()
                        self.stats.total_connections -= 1
                    
                    self.stats.active_connections = len(self.active_connections)
                    self.stats.idle_connections = len(self.idle_connections)
                    
                    # Notify waiting threads
                    self.condition.notify()
    
    def execute(self, query: str, params: tuple = ()) -> sqlite3.Cursor:
        """Execute query using pooled connection."""
        with self.get_connection() as conn:
            return conn.execute(query, params)
    
    def executemany(self, query: str, params_list: List[tuple]) -> sqlite3.Cursor:
        """Execute many queries in a batch."""
        with self.get_connection() as conn:
            cursor = conn.conn.cursor()
            cursor.executemany(query, params_list)
            conn.conn.commit()
            return cursor
    
    def get_stats(self) -> Dict[str, Any]:
        """Get pool statistics."""
        with self.lock:
            return {
                'total_connections': self.stats.total_connections,
                'active_connections': self.stats.active_connections,
                'idle_connections': self.stats.idle_connections,
                'total_requests': self.stats.total_requests,
                'cache_hit_rate': f"{self.stats.cache_hit_rate():.2f}%",
                'avg_wait_time_ms': f"{self.stats.avg_wait_time * 1000:.2f}",
            }
    
    def close_all(self):
        """Close all connections in the pool."""
        with self.lock:
            # Close idle connections
            while self.idle_connections:
                conn = self.idle_connections.popleft()
                conn.close()
            
            # Close active connections (should be empty)
            for conn in list(self.active_connections):
                conn.close()
            
            self.active_connections.clear()
            self.stats.total_connections = 0
            
        logger.info("Database pool closed")


# Global pool instances
_pools: Dict[str, DatabasePool] = {}
_pools_lock = threading.Lock()


def get_pool(db_path: str, **kwargs) -> DatabasePool:
    """
    Get or create a database pool for the given path.
    
    Args:
        db_path: Path to database
        **kwargs: Pool configuration options
    
    Returns:
        DatabasePool instance
    """
    with _pools_lock:
        if db_path not in _pools:
            _pools[db_path] = DatabasePool(db_path, **kwargs)
        return _pools[db_path]


def close_all_pools():
    """Close all database pools."""
    with _pools_lock:
        for pool in _pools.values():
            pool.close_all()
        _pools.clear()













