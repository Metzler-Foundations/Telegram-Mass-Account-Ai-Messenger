#!/usr/bin/env python3
"""
Database Connection Pool - Prevent connection exhaustion.

Features:
- Connection pooling for SQLite
- Automatic connection recycling
- Health checks
- Thread-safe operations
- Timeout handling
"""

import sqlite3
import threading
import time
import logging
from typing import Optional, Dict, Any
from pathlib import Path
from queue import Queue, Empty, Full
from contextlib import contextmanager
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class PooledConnection:
    """Wrapped database connection with metadata."""
    
    def __init__(self, connection: sqlite3.Connection, pool: 'ConnectionPool'):
        self.connection = connection
        self.pool = pool
        self.created_at = datetime.now()
        self.last_used = datetime.now()
        self.use_count = 0
        self.is_healthy = True
    
    def execute(self, *args, **kwargs):
        """Execute SQL with health checking."""
        try:
            self.last_used = datetime.now()
            self.use_count += 1
            return self.connection.execute(*args, **kwargs)
        except sqlite3.Error as e:
            logger.error(f"SQL execution error: {e}")
            self.is_healthy = False
            raise
    
    def executemany(self, *args, **kwargs):
        """Execute many SQL statements with lock retry."""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                self.last_used = datetime.now()
                self.use_count += 1
                return self.connection.executemany(*args, **kwargs)
            except sqlite3.OperationalError as e:
                if 'locked' in str(e).lower() and attempt < max_retries - 1:
                    wait_time = 0.5 * (2 ** attempt)
                    logger.warning(f"Database locked, retry {attempt + 1}/{max_retries} after {wait_time}s")
                    time.sleep(wait_time)
                else:
                    logger.error(f"SQL executemany error after {attempt + 1} attempts: {e}")
                    self.is_healthy = False
                    raise
            except sqlite3.Error as e:
                logger.error(f"SQL executemany error: {e}")
                self.is_healthy = False
                raise
    
    def commit(self):
        """Commit transaction with lock retry."""
        max_retries = 5
        for attempt in range(max_retries):
            try:
                return self.connection.commit()
            except sqlite3.OperationalError as e:
                if 'locked' in str(e).lower() and attempt < max_retries - 1:
                    wait_time = 0.5 * (2 ** attempt)
                    logger.warning(f"Database locked on commit, retry {attempt + 1}/{max_retries} after {wait_time}s")
                    time.sleep(wait_time)
                else:
                    logger.error(f"Commit error after {attempt + 1} attempts: {e}")
                    self.is_healthy = False
                    raise
            except sqlite3.Error as e:
                logger.error(f"Commit error: {e}")
                self.is_healthy = False
                raise
    
    def rollback(self):
        """Rollback transaction."""
        try:
            return self.connection.rollback()
        except sqlite3.Error as e:
            logger.error(f"Rollback error: {e}")
            self.is_healthy = False
            raise
    
    def cursor(self):
        """Get cursor."""
        return self.connection.cursor()
    
    def close(self):
        """Close connection."""
        try:
            self.connection.close()
        except Exception as e:
            logger.warning(f"Error closing connection: {e}")


class ConnectionPool:
    """SQLite connection pool manager."""
    
    def __init__(
        self,
        database: str,
        min_connections: int = 2,
        max_connections: int = 10,
        max_idle_time: int = 600,  # 10 minutes
        max_lifetime: int = 3600,  # 1 hour
        timeout: float = 30.0
    ):
        """
        Initialize connection pool.
        
        Args:
            database: Path to database file
            min_connections: Minimum number of connections to maintain
            max_connections: Maximum number of connections allowed
            max_idle_time: Max seconds a connection can be idle
            max_lifetime: Max seconds a connection can exist
            timeout: Timeout for getting connection from pool
        """
        self.database = database
        self.min_connections = min_connections
        self.max_connections = max_connections
        self.max_idle_time = max_idle_time
        self.max_lifetime = max_lifetime
        self.timeout = timeout
        
        # Connection queue
        self._pool: Queue = Queue(maxsize=max_connections)
        self._all_connections: list = []
        self._lock = threading.Lock()
        self._closed = False
        
        # Statistics
        self.stats = {
            'total_created': 0,
            'total_recycled': 0,
            'total_timeouts': 0,
            'total_errors': 0,
            'current_size': 0,
            'peak_size': 0
        }
        
        # Initialize minimum connections
        self._initialize_pool()
        
        # Start maintenance thread
        self._maintenance_thread = threading.Thread(
            target=self._maintenance_loop,
            daemon=True
        )
        self._maintenance_thread.start()
        
        logger.info(f"Connection pool initialized for {database} (min={min_connections}, max={max_connections})")
    
    def _create_connection(self) -> PooledConnection:
        """
        Create a new database connection.
        
        Returns:
            PooledConnection instance
        """
        try:
            # Enable WAL mode for better concurrency with extended timeout
            conn = sqlite3.connect(
                self.database,
                check_same_thread=False,
                timeout=60.0  # Increased from 30 to 60 seconds
            )
            
            # Configure connection for better lock handling
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("PRAGMA busy_timeout=60000")  # 60 seconds for better lock tolerance
            conn.execute("PRAGMA wal_autocheckpoint=1000")  # Checkpoint every 1000 pages
            conn.execute("PRAGMA cache_size=-64000")  # 64MB cache
            
            # Row factory for dict-like access
            conn.row_factory = sqlite3.Row
            
            pooled = PooledConnection(conn, self)
            
            with self._lock:
                self._all_connections.append(pooled)
                self.stats['total_created'] += 1
                self.stats['current_size'] = len(self._all_connections)
                self.stats['peak_size'] = max(self.stats['peak_size'], self.stats['current_size'])
            
            logger.debug(f"Created new connection (total: {self.stats['current_size']})")
            return pooled
            
        except Exception as e:
            self.stats['total_errors'] += 1
            logger.error(f"Failed to create connection: {e}")
            raise
    
    def _initialize_pool(self):
        """Initialize pool with minimum connections."""
        for _ in range(self.min_connections):
            try:
                conn = self._create_connection()
                self._pool.put(conn, block=False)
            except (Full, Exception) as e:
                logger.warning(f"Could not initialize all connections: {e}")
                break
    
    @contextmanager
    def get_connection(self):
        """
        Get a connection from the pool (context manager).
        
        Yields:
            PooledConnection instance
            
        Example:
            with pool.get_connection() as conn:
                conn.execute("SELECT * FROM table")
        """
        conn = None
        try:
            # Try to get from pool
            try:
                conn = self._pool.get(timeout=self.timeout)
            except Empty:
                # Pool empty, try to create new connection if under max
                with self._lock:
                    if len(self._all_connections) < self.max_connections:
                        conn = self._create_connection()
                    else:
                        # Wait for connection to become available
                        self.stats['total_timeouts'] += 1
                        raise TimeoutError(
                            f"Could not get connection within {self.timeout}s "
                            f"(pool size: {len(self._all_connections)})"
                        )
            
            # Check connection health
            if not self._is_connection_healthy(conn):
                logger.warning("Recycling unhealthy connection")
                self._recycle_connection(conn)
                conn = self._create_connection()
            
            yield conn
            
        finally:
            # Return connection to pool
            if conn:
                try:
                    # Rollback any uncommitted transactions
                    if conn.is_healthy:
                        try:
                            conn.rollback()
                        except Exception:
                            pass
                        
                        # Return to pool
                        self._pool.put(conn, block=False)
                    else:
                        # Recycle unhealthy connection
                        self._recycle_connection(conn)
                except Full:
                    # Pool full, close connection
                    self._recycle_connection(conn)
    
    def _is_connection_healthy(self, conn: PooledConnection) -> bool:
        """
        Check if connection is healthy.
        
        Args:
            conn: Connection to check
            
        Returns:
            True if healthy
        """
        if not conn.is_healthy:
            return False
        
        # Check age
        age = (datetime.now() - conn.created_at).total_seconds()
        if age > self.max_lifetime:
            logger.debug(f"Connection exceeded max lifetime ({age}s)")
            return False
        
        # Check idle time
        idle_time = (datetime.now() - conn.last_used).total_seconds()
        if idle_time > self.max_idle_time:
            logger.debug(f"Connection exceeded max idle time ({idle_time}s)")
            return False
        
        # Test with ping
        try:
            conn.execute("SELECT 1").fetchone()
            return True
        except Exception as e:
            logger.warning(f"Connection health check failed: {e}")
            return False
    
    def _recycle_connection(self, conn: PooledConnection):
        """
        Recycle (close) a connection.
        
        Args:
            conn: Connection to recycle
        """
        try:
            conn.close()
            
            with self._lock:
                if conn in self._all_connections:
                    self._all_connections.remove(conn)
                self.stats['total_recycled'] += 1
                self.stats['current_size'] = len(self._all_connections)
            
            logger.debug(f"Recycled connection (total: {self.stats['current_size']})")
        except Exception as e:
            logger.warning(f"Error recycling connection: {e}")
    
    def _maintenance_loop(self):
        """Background maintenance loop."""
        while not self._closed:
            try:
                time.sleep(60)  # Run every minute
                self._maintenance_pass()
            except Exception as e:
                logger.error(f"Maintenance error: {e}")
    
    def _maintenance_pass(self):
        """Perform maintenance on pool."""
        if self._closed:
            return
        
        # Collect connections to recycle
        to_recycle = []
        
        with self._lock:
            for conn in self._all_connections:
                if not self._is_connection_healthy(conn):
                    to_recycle.append(conn)
        
        # Recycle unhealthy connections
        for conn in to_recycle:
            try:
                # Try to get from pool to recycle
                pool_conn = self._pool.get(block=False)
                if pool_conn == conn:
                    self._recycle_connection(conn)
            except Empty:
                pass
        
        # Ensure minimum connections
        current_size = len(self._all_connections)
        if current_size < self.min_connections:
            needed = self.min_connections - current_size
            logger.info(f"Replenishing pool (current: {current_size}, min: {self.min_connections})")
            for _ in range(needed):
                try:
                    conn = self._create_connection()
                    self._pool.put(conn, block=False)
                except (Full, Exception) as e:
                    logger.warning(f"Could not replenish connection: {e}")
                    break
    
    def close(self):
        """Close all connections in pool."""
        self._closed = True
        
        logger.info("Closing connection pool...")
        
        # Close all connections
        with self._lock:
            for conn in self._all_connections:
                try:
                    conn.close()
                except Exception as e:
                    logger.warning(f"Error closing connection: {e}")
            
            self._all_connections.clear()
            self.stats['current_size'] = 0
        
        # Clear pool queue
        while not self._pool.empty():
            try:
                self._pool.get(block=False)
            except Empty:
                break
        
        logger.info(f"Connection pool closed. Stats: {self.stats}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get pool statistics."""
        with self._lock:
            return {
                **self.stats,
                'pool_size': self._pool.qsize(),
                'connections_available': self._pool.qsize(),
                'connections_in_use': len(self._all_connections) - self._pool.qsize()
            }


# Global pool instances
_pools: Dict[str, ConnectionPool] = {}
_pools_lock = threading.Lock()


def get_pool(database: str, **kwargs) -> ConnectionPool:
    """
    Get or create connection pool for database.
    
    Args:
        database: Database path
        **kwargs: ConnectionPool arguments
        
    Returns:
        ConnectionPool instance
    """
    with _pools_lock:
        if database not in _pools:
            _pools[database] = ConnectionPool(database, **kwargs)
        return _pools[database]


def close_all_pools():
    """Close all connection pools."""
    with _pools_lock:
        for pool in _pools.values():
            try:
                pool.close()
            except Exception as e:
                logger.error(f"Error closing pool: {e}")
        _pools.clear()


# Register cleanup on exit
import atexit
atexit.register(close_all_pools)




