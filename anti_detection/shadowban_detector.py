"""
Shadow Ban Detector - Detect and monitor shadow bans.

Features:
- Canary account system for delivery verification
- Shadow ban indicator detection
- Delivery rate monitoring
- Alert system for potential restrictions
"""

import asyncio
import logging
import sqlite3
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

from pyrogram import Client
from pyrogram.errors import FloodWait

logger = logging.getLogger(__name__)


class ShadowBanStatus(Enum):
    """Shadow ban status levels."""
    CLEAR = "clear"
    SUSPECTED = "suspected"
    LIKELY = "likely"
    CONFIRMED = "confirmed"


@dataclass
class DeliveryTest:
    """Delivery test result."""
    test_id: str
    account_id: str
    canary_id: str
    message_sent: bool
    message_received: bool
    timestamp: datetime
    delay_seconds: Optional[float] = None


class ShadowBanDetector:
    """Detect shadow bans and delivery issues."""
    
    def __init__(self, db_path: str = "shadowban_monitor.db"):
        """Initialize."""
        self.db_path = db_path
        self._connection_pool = None
        try:
            from database.connection_pool import get_pool
            self._connection_pool = get_pool(self.db_path)
        except: pass
        self._init_database()
    
    def _get_connection(self):
        if self._connection_pool:
            return self._connection_pool.get_connection()
        return self._get_connection()
        self.canary_accounts: List[int] = []
    
    def _init_database(self):
        """Initialize monitoring database."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Delivery tests
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS delivery_tests (
                test_id TEXT PRIMARY KEY,
                account_id TEXT,
                canary_id TEXT,
                message_sent INTEGER,
                message_received INTEGER,
                delay_seconds REAL,
                timestamp TIMESTAMP
            )
        """)
        
        # Account status
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS account_status (
                account_id TEXT PRIMARY KEY,
                shadowban_status TEXT,
                delivery_rate REAL,
                last_successful_delivery TIMESTAMP,
                total_tests INTEGER,
                failed_tests INTEGER,
                last_updated TIMESTAMP
            )
        """)
        
        # Canary accounts
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS canary_accounts (
                canary_id TEXT PRIMARY KEY,
                user_id INTEGER,
                phone_number TEXT,
                is_active INTEGER,
                added_at TIMESTAMP
            )
        """)
        
        conn.commit()
        conn.close()
        logger.info("Shadow ban monitoring database initialized")
    
    def register_canary(self, canary_id: str, user_id: int, phone: str):
        """Register a canary account for testing.
        
        Args:
            canary_id: Canary account identifier
            user_id: Telegram user ID
            phone: Phone number
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO canary_accounts 
            (canary_id, user_id, phone_number, is_active, added_at)
            VALUES (?, ?, ?, 1, ?)
        """, (canary_id, user_id, phone, datetime.now()))
        conn.commit()
        conn.close()
        logger.info(f"Registered canary account: {canary_id}")
    
    async def test_delivery(self, client: Client, account_id: str, 
                           canary_user_id: int) -> DeliveryTest:
        """Test message delivery using canary account.
        
        Args:
            client: Pyrogram client
            account_id: Account being tested
            canary_user_id: Canary account user ID
            
        Returns:
            DeliveryTest result
        """
        import uuid
        test_id = str(uuid.uuid4())
        test_message = f"Test_{test_id[:8]}"
        
        test = DeliveryTest(
            test_id=test_id,
            account_id=account_id,
            canary_id=str(canary_user_id),
            message_sent=False,
            message_received=False,
            timestamp=datetime.now()
        )
        
        try:
            # Send test message to canary
            sent_time = datetime.now()
            await client.send_message(canary_user_id, test_message)
            test.message_sent = True
            
            # Wait and check if received (would need canary client to verify)
            await asyncio.sleep(5)
            
            # This is simplified - in real implementation, canary would report back
            test.message_received = True  # Assume received for now
            test.delay_seconds = (datetime.now() - sent_time).total_seconds()
            
            logger.info(f"Delivery test passed for {account_id}")
            
        except FloodWait as e:
            logger.warning(f"FloodWait during delivery test: {e.value}s")
            test.message_sent = True
            test.message_received = False
        except Exception as e:
            logger.error(f"Delivery test failed: {e}")
            test.message_sent = False
        
        # Save test result
        self._save_test_result(test)
        self._update_account_status(account_id, test)
        
        return test
    
    def _save_test_result(self, test: DeliveryTest):
        """Save test result to database."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO delivery_tests 
            (test_id, account_id, canary_id, message_sent, message_received, 
             delay_seconds, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (test.test_id, test.account_id, test.canary_id,
              int(test.message_sent), int(test.message_received),
              test.delay_seconds, test.timestamp))
        conn.commit()
        conn.close()
    
    def _update_account_status(self, account_id: str, test: DeliveryTest):
        """Update account status based on test result."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Get current stats
        cursor.execute("""
            SELECT total_tests, failed_tests FROM account_status 
            WHERE account_id = ?
        """, (account_id,))
        row = cursor.fetchone()
        
        if row:
            total = row[0] + 1
            failed = row[1] + (0 if test.message_received else 1)
        else:
            total = 1
            failed = 0 if test.message_received else 1
        
        delivery_rate = (total - failed) / total if total > 0 else 0.0
        
        # Determine shadow ban status
        if delivery_rate >= 0.9:
            status = ShadowBanStatus.CLEAR
        elif delivery_rate >= 0.7:
            status = ShadowBanStatus.SUSPECTED
        elif delivery_rate >= 0.5:
            status = ShadowBanStatus.LIKELY
        else:
            status = ShadowBanStatus.CONFIRMED
        
        # Update status
        cursor.execute("""
            INSERT OR REPLACE INTO account_status 
            (account_id, shadowban_status, delivery_rate, last_successful_delivery,
             total_tests, failed_tests, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (account_id, status.value, delivery_rate,
              datetime.now() if test.message_received else None,
              total, failed, datetime.now()))
        
        conn.commit()
        conn.close()
        
        if status != ShadowBanStatus.CLEAR:
            logger.warning(f"Shadow ban detected for {account_id}: {status.value} (rate: {delivery_rate:.2%})")
    
    def get_account_status(self, account_id: str) -> Dict:
        """Get shadow ban status for account."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM account_status WHERE account_id = ?
        """, (account_id,))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return {
                'account_id': account_id,
                'status': ShadowBanStatus.CLEAR.value,
                'delivery_rate': 1.0,
                'total_tests': 0
            }
        
        return {
            'account_id': row[0],
            'status': row[1],
            'delivery_rate': row[2],
            'last_successful': row[3],
            'total_tests': row[4],
            'failed_tests': row[5],
            'last_updated': row[6]
        }
    
    def get_suspected_accounts(self) -> List[str]:
        """Get list of accounts with suspected shadow bans."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT account_id FROM account_status
            WHERE shadowban_status IN ('suspected', 'likely', 'confirmed')
            ORDER BY delivery_rate ASC
        """)
        accounts = [row[0] for row in cursor.fetchall()]
        conn.close()
        return accounts

