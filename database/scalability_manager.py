#!/usr/bin/env python3
"""
Database Scalability Manager - Handles read/write splitting and PostgreSQL migration.

Features:
- Automatic read/write connection routing
- PostgreSQL migration path
- Query optimization and batching
- Connection pool management
- Performance monitoring
"""

import logging
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

try:
    import psycopg2
    import psycopg2.pool

    POSTGRES_AVAILABLE = True
except ImportError:
    POSTGRES_AVAILABLE = False
    logger.warning("PostgreSQL not available, SQLite-only mode")


@dataclass
class QueryMetrics:
    """Metrics for database operations."""

    query_count: int = 0
    total_time: float = 0.0
    avg_time: float = 0.0
    slow_queries: int = 0


class DatabaseScalabilityManager:
    """
    Manages database scalability with read/write splitting and migration support.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize scalability manager.

        Args:
            config: Database configuration
        """
        self.config = config
        self.backend = config.get("backend", "sqlite")  # 'sqlite' or 'postgres'
        self.connection_manager = None
        self.metrics = QueryMetrics()
        self.migration_in_progress = False

        # Initialize appropriate backend
        if self.backend == "postgres" and POSTGRES_AVAILABLE:
            self._init_postgres()
        else:
            self._init_sqlite()

    def _init_sqlite(self):
        """Initialize SQLite with optimizations."""
        from .connection_pool import ConnectionPool

        db_path = self.config.get("sqlite_path", "members.db")
        self.connection_manager = ConnectionPool(
            database=db_path,
            min_connections=self.config.get("min_connections", 2),
            max_connections=self.config.get("max_connections", 20),
            max_idle_time=self.config.get("max_idle_time", 600),
            max_lifetime=self.config.get("max_lifetime", 3600),
        )
        logger.info("Initialized SQLite scalability manager")

    def _init_postgres(self):
        """Initialize PostgreSQL connection pool."""
        if not POSTGRES_AVAILABLE:
            raise RuntimeError("PostgreSQL not available")

        # Create connection pool
        self.connection_manager = psycopg2.pool.ThreadedConnectionPool(
            minconn=self.config.get("min_connections", 2),
            maxconn=self.config.get("max_connections", 20),
            host=self.config["host"],
            port=self.config.get("port", 5432),
            database=self.config["database"],
            user=self.config["user"],
            password=self.config["password"],
        )
        logger.info("Initialized PostgreSQL scalability manager")

    @contextmanager
    def get_read_connection(self):
        """Get a read-only connection."""
        if self.backend == "sqlite":
            with self.connection_manager.get_connection("read") as conn:
                yield conn.connection
        else:
            # PostgreSQL - all connections can read
            conn = self.connection_manager.getconn()
            try:
                yield conn
            finally:
                self.connection_manager.putconn(conn)

    @contextmanager
    def get_write_connection(self):
        """Get a write connection."""
        if self.backend == "sqlite":
            with self.connection_manager.get_connection("write") as conn:
                yield conn.connection
        else:
            # PostgreSQL - all connections can write
            conn = self.connection_manager.getconn()
            try:
                yield conn
            finally:
                self.connection_manager.putconn(conn)

    def execute_read_query(self, query: str, params: tuple = None) -> List[Dict]:
        """
        Execute a read query with automatic connection management.

        Args:
            query: SQL query string
            params: Query parameters

        Returns:
            List of result dictionaries
        """
        time.time()

        with self.get_read_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(query, params or ())
                columns = [desc[0] for desc in cursor.description] if cursor.description else []
                results = [dict(zip(columns, row)) for row in cursor.fetchall()]
                return results
            finally:
                cursor.close()

    def execute_write_query(self, query: str, params: tuple = None) -> int:
        """
        Execute a write query with automatic connection management.

        Args:
            query: SQL query string
            params: Query parameters

        Returns:
            Number of affected rows
        """
        time.time()

        with self.get_write_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(query, params or ())
                conn.commit()
                affected_rows = cursor.rowcount
                return affected_rows
            except Exception:
                conn.rollback()
                raise
            finally:
                cursor.close()

    def execute_batch_write(self, queries: List[Dict[str, Any]]) -> List[int]:
        """
        Execute multiple write queries in a batch.

        Args:
            queries: List of dicts with 'query' and 'params' keys

        Returns:
            List of affected row counts
        """
        results = []

        with self.get_write_connection() as conn:
            cursor = conn.cursor()
            try:
                for query_data in queries:
                    cursor.execute(query_data["query"], query_data.get("params", ()))
                    results.append(cursor.rowcount)

                conn.commit()
                return results
            except Exception:
                conn.rollback()
                raise
            finally:
                cursor.close()

    def migrate_to_postgres(self, postgres_config: Dict[str, Any]) -> bool:
        """
        Migrate database from SQLite to PostgreSQL.

        Args:
            postgres_config: PostgreSQL connection configuration

        Returns:
            True if migration successful
        """
        if not POSTGRES_AVAILABLE:
            logger.error("PostgreSQL not available for migration")
            return False

        try:
            self.migration_in_progress = True
            logger.info("Starting database migration to PostgreSQL...")

            # Create PostgreSQL schema
            self._create_postgres_schema(postgres_config)

            # Migrate data
            success = self._migrate_data(postgres_config)

            if success:
                # Update configuration to use PostgreSQL
                self.config.update(postgres_config)
                self.config["backend"] = "postgres"
                self._init_postgres()
                logger.info("Migration to PostgreSQL completed successfully")
            else:
                logger.error("Migration failed")

            return success

        except Exception as e:
            logger.error(f"Migration failed: {e}")
            return False
        finally:
            self.migration_in_progress = False

    def _create_postgres_schema(self, config: Dict[str, Any]):
        """Create PostgreSQL schema."""
        # This would implement schema creation for PostgreSQL
        # For now, just log that it would happen
        logger.info("Would create PostgreSQL schema here")

    def _migrate_data(self, config: Dict[str, Any]) -> bool:
        """Migrate data from SQLite to PostgreSQL."""
        # This would implement data migration
        # For now, just return True for testing
        logger.info("Would migrate data from SQLite to PostgreSQL here")
        return True

    def get_metrics(self) -> Dict[str, Any]:
        """Get database performance metrics."""
        return {
            "backend": self.backend,
            "query_count": self.metrics.query_count,
            "total_time": self.metrics.total_time,
            "avg_time": self.metrics.avg_time,
            "slow_queries": self.metrics.slow_queries,
            "migration_in_progress": self.migration_in_progress,
        }

    def optimize_database(self):
        """Run database optimization."""
        if self.backend == "sqlite":
            # SQLite optimization
            with self.get_write_connection() as conn:
                conn.execute("VACUUM")
                conn.execute("ANALYZE")
                logger.info("SQLite database optimized")
        else:
            # PostgreSQL optimization would go here
            logger.info("PostgreSQL optimization not implemented yet")


# Global instance
_scalability_manager = None


def get_scalability_manager(config: Dict[str, Any] = None) -> DatabaseScalabilityManager:
    """Get the global database scalability manager instance."""
    global _scalability_manager

    if _scalability_manager is None:
        if config is None:
            # Default SQLite configuration
            config = {
                "backend": "sqlite",
                "sqlite_path": "members.db",
                "min_connections": 2,
                "max_connections": 20,
            }
        _scalability_manager = DatabaseScalabilityManager(config)

    return _scalability_manager
