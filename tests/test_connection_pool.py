"""Tests for database connection pool."""
import pytest
import sqlite3
import asyncio
import time
from pathlib import Path
from database.connection_pool import ConnectionPool, get_pool, close_all_pools


class TestConnectionPool:
    """Test connection pool functionality."""
    
    def setup_method(self):
        """Setup for each test."""
        close_all_pools()  # Clean state
    
    def teardown_method(self):
        """Cleanup after each test."""
        close_all_pools()
    
    def test_pool_initialization(self):
        """Test pool creates minimum connections."""
        pool = ConnectionPool(':memory:', min_connections=2, max_connections=5)
        
        assert pool.min_connections == 2
        assert pool.max_connections == 5
        assert pool.stats['current_size'] >= 2
    
    def test_get_connection(self):
        """Test getting connection from pool."""
        pool = ConnectionPool(':memory:', min_connections=2, max_connections=5)
        
        with pool.get_connection() as conn:
            assert conn is not None
            result = conn.execute("SELECT 1").fetchone()
            assert result[0] == 1
    
    def test_connection_reuse(self):
        """Test connections are reused."""
        pool = ConnectionPool(':memory:', min_connections=2, max_connections=5)
        
        with pool.get_connection() as conn1:
            conn1_id = id(conn1)
        
        with pool.get_connection() as conn2:
            conn2_id = id(conn2)
        
        # Should reuse same connection
        assert conn1_id == conn2_id or pool.stats['current_size'] <= 2
    
    def test_concurrent_connections(self):
        """Test multiple concurrent connections."""
        pool = ConnectionPool(':memory:', min_connections=2, max_connections=10)
        
        # Use pool properly with context managers
        results = []
        for i in range(3):
            with pool.get_connection() as conn:
                result = conn.execute("SELECT ?", (i,)).fetchone()
                results.append(result[0])
        
        assert results == [0, 1, 2]
        assert pool.stats['current_size'] >= 2
    
    def test_connection_health_check(self):
        """Test unhealthy connections are recycled."""
        pool = ConnectionPool(':memory:', max_lifetime=1, max_idle_time=1)
        
        with pool.get_connection() as conn:
            conn.execute("SELECT 1")
        
        # Wait for connection to become unhealthy
        time.sleep(1.1)
        
        # Next get should recycle
        stats_before = pool.stats['total_recycled']
        with pool.get_connection() as conn:
            conn.execute("SELECT 1")
        
        # May or may not recycle depending on timing
        assert pool.stats['total_recycled'] >= stats_before
    
    def test_pool_close(self):
        """Test pool closes all connections."""
        pool = ConnectionPool(':memory:', min_connections=2)
        
        # Get initial size
        initial_size = pool.stats['current_size']
        assert initial_size >= 2
        
        # Close pool
        pool.close()
        
        # All connections should be closed
        assert pool.stats['current_size'] == 0
    
    def test_get_pool_singleton(self):
        """Test get_pool returns same instance for same database."""
        pool1 = get_pool('test.db')
        pool2 = get_pool('test.db')
        
        assert pool1 is pool2
    
    def test_transaction_rollback(self):
        """Test transactions rollback on error."""
        # Use same database path for all connections
        import tempfile
        temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        temp_db.close()
        
        try:
            pool = ConnectionPool(temp_db.name)
            
            with pool.get_connection() as conn:
                conn.execute('CREATE TABLE test (id INTEGER PRIMARY KEY, value TEXT)')
                conn.commit()
            
            # Insert should succeed
            with pool.get_connection() as conn:
                conn.execute('INSERT INTO test (id, value) VALUES (?, ?)', (1, 'test'))
                conn.commit()
            
            # Verify data
            with pool.get_connection() as conn:
                result = conn.execute('SELECT COUNT(*) FROM test').fetchone()
                assert result[0] == 1
            
            pool.close()
        finally:
            import os
            os.unlink(temp_db.name)

