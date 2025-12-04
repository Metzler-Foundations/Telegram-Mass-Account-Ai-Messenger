#!/usr/bin/env python3
"""
Database Migration System - Schema version management.

Features:
- Version-based migrations
- Rollback support
- Migration history tracking
- Schema validation
- Automatic backup before migration
"""

import sqlite3
import logging
import hashlib
from pathlib import Path
from datetime import datetime
from typing import List, Callable, Optional, Dict
import shutil

logger = logging.getLogger(__name__)


class Migration:
    """Represents a single database migration."""
    
    def __init__(
        self,
        version: int,
        name: str,
        up: Callable,
        down: Optional[Callable] = None
    ):
        """
        Initialize migration.
        
        Args:
            version: Migration version number
            name: Migration name/description
            up: Function to apply migration
            down: Function to rollback migration (optional)
        """
        self.version = version
        self.name = name
        self.up = up
        self.down = down
    
    def __repr__(self):
        return f"Migration(v{self.version}: {self.name})"


class MigrationManager:
    """
    Manages database schema migrations.
    
    Ensures database schema can evolve without breaking existing deployments.
    """
    
    def __init__(self, database_path: str):
        """
        Initialize migration manager.
        
        Args:
            database_path: Path to database file
        """
        self.database_path = database_path
        self.migrations: List[Migration] = []
        
        # Initialize migration tracking table
        self._init_migration_table()
    
    def _init_migration_table(self):
        """Create migration tracking table if not exists."""
        try:
            conn = sqlite3.connect(self.database_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    checksum TEXT,
                    applied_by TEXT
                )
            """)
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Failed to initialize migration table: {e}")
    
    def register_migration(self, migration: Migration):
        """
        Register a migration.
        
        Args:
            migration: Migration to register
        """
        self.migrations.append(migration)
        self.migrations.sort(key=lambda m: m.version)
        logger.debug(f"Registered migration: {migration}")
    
    def get_current_version(self) -> int:
        """
        Get current database schema version.
        
        Returns:
            Current version number (0 if no migrations applied)
        """
        try:
            conn = sqlite3.connect(self.database_path)
            cursor = conn.cursor()
            
            cursor.execute(
                "SELECT MAX(version) FROM schema_migrations"
            )
            result = cursor.fetchone()
            conn.close()
            
            return result[0] if result[0] is not None else 0
            
        except Exception as e:
            logger.warning(f"Could not determine version: {e}")
            return 0
    
    def get_pending_migrations(self) -> List[Migration]:
        """
        Get list of pending migrations.
        
        Returns:
            List of migrations not yet applied
        """
        current_version = self.get_current_version()
        return [m for m in self.migrations if m.version > current_version]
    
    def migrate(self, target_version: Optional[int] = None) -> bool:
        """
        Run pending migrations.
        
        Args:
            target_version: Target version (None = latest)
            
        Returns:
            True if successful
        """
        current_version = self.get_current_version()
        pending = self.get_pending_migrations()
        
        if not pending:
            logger.info(f"Database is up to date (version {current_version})")
            return True
        
        if target_version:
            pending = [m for m in pending if m.version <= target_version]
        
        logger.info(f"Running {len(pending)} pending migrations...")
        
        # Backup database before migration
        if not self._backup_database():
            logger.error("Backup failed, aborting migration")
            return False
        
        # Apply migrations
        for migration in pending:
            if not self._apply_migration(migration):
                logger.error(f"Migration failed: {migration}")
                return False
        
        logger.info(f"✅ All migrations complete. Version: {self.get_current_version()}")
        return True
    
    def _apply_migration(self, migration: Migration) -> bool:
        """
        Apply a single migration.
        
        Args:
            migration: Migration to apply
            
        Returns:
            True if successful
        """
        logger.info(f"Applying migration: {migration}")
        
        try:
            conn = sqlite3.connect(self.database_path)
            cursor = conn.cursor()
            
            # Begin transaction
            cursor.execute("BEGIN IMMEDIATE")
            
            # Run migration
            migration.up(conn)
            
            # Record migration
            cursor.execute("""
                INSERT INTO schema_migrations (version, name, checksum, applied_by)
                VALUES (?, ?, ?, ?)
            """, (
                migration.version,
                migration.name,
                self._calculate_checksum(migration),
                "system"
            ))
            
            # Commit
            conn.commit()
            conn.close()
            
            logger.info(f"✅ Migration v{migration.version} applied successfully")
            return True
            
        except Exception as e:
            logger.error(f"Migration failed: {e}", exc_info=True)
            
            try:
                conn.rollback()
                conn.close()
            except Exception:
                pass
            
            return False
    
    def rollback(self, target_version: int) -> bool:
        """
        Rollback to specific version.
        
        Args:
            target_version: Version to rollback to
            
        Returns:
            True if successful
        """
        current_version = self.get_current_version()
        
        if target_version >= current_version:
            logger.warning(f"Target version {target_version} >= current {current_version}")
            return True
        
        # Get migrations to rollback (in reverse order)
        to_rollback = [
            m for m in self.migrations
            if target_version < m.version <= current_version
        ]
        to_rollback.reverse()
        
        logger.info(f"Rolling back {len(to_rollback)} migrations...")
        
        # Backup before rollback
        if not self._backup_database():
            logger.error("Backup failed, aborting rollback")
            return False
        
        # Rollback migrations
        for migration in to_rollback:
            if not migration.down:
                logger.error(f"Migration v{migration.version} has no rollback function")
                return False
            
            if not self._rollback_migration(migration):
                logger.error(f"Rollback failed: {migration}")
                return False
        
        logger.info(f"✅ Rollback complete. Version: {self.get_current_version()}")
        return True
    
    def _rollback_migration(self, migration: Migration) -> bool:
        """
        Rollback a single migration.
        
        Args:
            migration: Migration to rollback
            
        Returns:
            True if successful
        """
        logger.info(f"Rolling back migration: {migration}")
        
        try:
            conn = sqlite3.connect(self.database_path)
            cursor = conn.cursor()
            
            # Begin transaction
            cursor.execute("BEGIN IMMEDIATE")
            
            # Run rollback
            migration.down(conn)
            
            # Remove from history
            cursor.execute(
                "DELETE FROM schema_migrations WHERE version = ?",
                (migration.version,)
            )
            
            # Commit
            conn.commit()
            conn.close()
            
            logger.info(f"✅ Migration v{migration.version} rolled back")
            return True
            
        except Exception as e:
            logger.error(f"Rollback failed: {e}", exc_info=True)
            
            try:
                conn.rollback()
                conn.close()
            except Exception:
                pass
            
            return False
    
    def _backup_database(self) -> bool:
        """
        Create database backup before migration.
        
        Returns:
            True if successful
        """
        try:
            db_path = Path(self.database_path)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = db_path.with_name(f"{db_path.stem}_backup_{timestamp}.db")
            
            shutil.copy2(db_path, backup_path)
            logger.info(f"Database backed up to: {backup_path}")
            return True
            
        except Exception as e:
            logger.error(f"Backup failed: {e}")
            return False
    
    def _calculate_checksum(self, migration: Migration) -> str:
        """
        Calculate checksum for migration.
        
        Args:
            migration: Migration to checksum
            
        Returns:
            SHA256 checksum
        """
        content = f"{migration.version}:{migration.name}"
        return hashlib.sha256(content.encode()).hexdigest()
    
    def get_migration_history(self) -> List[Dict]:
        """
        Get migration history.
        
        Returns:
            List of applied migrations
        """
        try:
            conn = sqlite3.connect(self.database_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT version, name, applied_at, checksum, applied_by
                FROM schema_migrations
                ORDER BY version
            """)
            
            results = cursor.fetchall()
            conn.close()
            
            return [
                {
                    'version': r[0],
                    'name': r[1],
                    'applied_at': r[2],
                    'checksum': r[3],
                    'applied_by': r[4]
                }
                for r in results
            ]
            
        except Exception as e:
            logger.error(f"Failed to get migration history: {e}")
            return []


# Example migrations
def migration_001_add_unique_constraints(conn: sqlite3.Connection):
    """Migration 001: Add unique constraints to prevent duplicates."""
    cursor = conn.cursor()
    
    # Add unique constraint to proxy_assignments
    cursor.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_proxy_assignment_unique
        ON proxy_assignments(account_id, proxy_id)
    """)
    
    # Add unique constraint to campaign_messages
    cursor.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_campaign_message_unique
        ON campaign_messages(campaign_id, target_user_id, message_hash)
    """)
    
    logger.info("Added unique constraints")


def migration_002_add_idempotency_keys(conn: sqlite3.Connection):
    """Migration 002: Add idempotency keys for duplicate prevention."""
    cursor = conn.cursor()
    
    # Add idempotency_key column to campaign_messages
    cursor.execute("""
        ALTER TABLE campaign_messages
        ADD COLUMN idempotency_key TEXT
    """)
    
    # Create index on idempotency_key
    cursor.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_campaign_message_idempotency
        ON campaign_messages(idempotency_key)
    """)
    
    logger.info("Added idempotency keys")


# Register migrations
def setup_migrations(manager: MigrationManager):
    """Setup all migrations."""
    manager.register_migration(Migration(
        version=1,
        name="add_unique_constraints",
        up=migration_001_add_unique_constraints
    ))
    
    manager.register_migration(Migration(
        version=2,
        name="add_idempotency_keys",
        up=migration_002_add_idempotency_keys
    ))


if __name__ == "__main__":
    # Test migration system
    manager = MigrationManager("test.db")
    setup_migrations(manager)
    
    print(f"Current version: {manager.get_current_version()}")
    print(f"Pending migrations: {manager.get_pending_migrations()}")
    
    # Run migrations
    manager.migrate()
    
    # Show history
    print("Migration history:")
    for m in manager.get_migration_history():
        print(f"  v{m['version']}: {m['name']} (applied: {m['applied_at']})")


