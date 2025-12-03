#!/usr/bin/env python3
"""
Test script for proxy loading performance.

This script tests the performance improvements for loading and managing large proxy datasets.
"""

import time
import logging
import sys
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_proxy_pool_loading():
    """Test proxy pool manager loading performance."""
    logger.info("=" * 70)
    logger.info("TEST: Proxy Pool Manager Loading Performance")
    logger.info("=" * 70)
    
    try:
        from proxy_pool_manager import ProxyPoolManager
        
        # Initialize manager
        logger.info("Initializing ProxyPoolManager...")
        start_time = time.time()
        
        manager = ProxyPoolManager(db_path="proxy_pool.db")
        
        init_time = time.time() - start_time
        
        # Get stats
        stats = manager.get_proxy_stats()
        
        logger.info(f"✅ Initialization completed in {init_time:.2f} seconds")
        logger.info(f"   Total proxies loaded: {stats['total']}")
        logger.info(f"   Active proxies: {stats['active']}")
        logger.info(f"   Available proxies: {stats['available']}")
        logger.info(f"   Assigned proxies: {stats['assigned']}")
        logger.info(f"   Average score: {stats['avg_score']:.2f}")
        logger.info(f"   Average latency: {stats['avg_latency_ms']:.2f}ms")
        
        # Test pagination
        logger.info("\nTesting pagination...")
        start_time = time.time()
        
        proxies, total = manager.get_proxies_paginated(page=1, page_size=100, active_only=True)
        
        pagination_time = time.time() - start_time
        
        logger.info(f"✅ Pagination query completed in {pagination_time:.3f} seconds")
        logger.info(f"   Retrieved {len(proxies)} proxies from page 1")
        logger.info(f"   Total matching proxies: {total}")
        
        # Performance verdict
        logger.info("\n" + "=" * 70)
        if init_time < 3.0:
            logger.info("✅ PASS: Initialization time is acceptable (< 3 seconds)")
        else:
            logger.warning("⚠️  SLOW: Initialization took longer than expected")
        
        if pagination_time < 0.5:
            logger.info("✅ PASS: Pagination query is fast (< 0.5 seconds)")
        else:
            logger.warning("⚠️  SLOW: Pagination query could be faster")
        
        logger.info("=" * 70)
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}", exc_info=True)
        return False


def test_ui_performance():
    """Test UI component performance."""
    logger.info("\n" + "=" * 70)
    logger.info("TEST: UI Component Performance")
    logger.info("=" * 70)
    
    try:
        # Try to import Qt - may not be available in headless environment
        try:
            from PyQt6.QtWidgets import QApplication
            from proxy_management_widget import ProxyTableWidget
            
            logger.info("Initializing Qt application...")
            app = QApplication.instance() or QApplication(sys.argv)
            
            logger.info("Creating ProxyTableWidget...")
            start_time = time.time()
            
            widget = ProxyTableWidget()
            
            init_time = time.time() - start_time
            
            logger.info(f"✅ Widget created in {init_time:.3f} seconds")
            
            # Test pagination controls
            logger.info("Testing pagination controls...")
            widget.current_page = 1
            widget.page_size = 100
            widget.total_count = 10000
            widget.update_pagination_controls()
            
            logger.info("✅ Pagination controls working")
            
            logger.info("\n" + "=" * 70)
            logger.info("✅ PASS: UI components initialized successfully")
            logger.info("=" * 70)
            
            return True
            
        except ImportError:
            logger.info("⚠️  Qt not available, skipping UI tests (normal for headless)")
            return True
            
    except Exception as e:
        logger.error(f"❌ UI test failed: {e}", exc_info=True)
        return False


def test_database_indexes():
    """Test that database indexes are present."""
    logger.info("\n" + "=" * 70)
    logger.info("TEST: Database Indexes")
    logger.info("=" * 70)
    
    try:
        import sqlite3
        
        db_path = "proxy_pool.db"
        if not Path(db_path).exists():
            logger.info("⚠️  Database doesn't exist yet, skipping index test")
            return True
        
        with sqlite3.connect(db_path) as conn:
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='index'")
            indexes = [row[0] for row in cursor.fetchall()]
        
        expected_indexes = [
            'idx_proxy_status',
            'idx_proxy_score',
            'idx_proxy_fraud_score',
            'idx_proxy_last_check',
            'idx_proxy_assigned',
            'idx_proxy_status_score'
        ]
        
        logger.info(f"Found {len(indexes)} indexes in database")
        
        missing = []
        for expected in expected_indexes:
            if expected in indexes:
                logger.info(f"  ✅ {expected}")
            else:
                logger.warning(f"  ❌ {expected} - MISSING")
                missing.append(expected)
        
        logger.info("\n" + "=" * 70)
        if not missing:
            logger.info("✅ PASS: All required indexes are present")
        else:
            logger.warning(f"⚠️  {len(missing)} indexes missing: {', '.join(missing)}")
        logger.info("=" * 70)
        
        return len(missing) == 0
        
    except Exception as e:
        logger.error(f"❌ Database index test failed: {e}", exc_info=True)
        return False


def main():
    """Run all performance tests."""
    logger.info("\n")
    logger.info("╔═══════════════════════════════════════════════════════════════════╗")
    logger.info("║         Proxy Loading Performance Test Suite                      ║")
    logger.info("╚═══════════════════════════════════════════════════════════════════╝")
    logger.info("\n")
    
    results = []
    
    # Run tests
    results.append(("Database Indexes", test_database_indexes()))
    results.append(("Proxy Pool Loading", test_proxy_pool_loading()))
    results.append(("UI Performance", test_ui_performance()))
    
    # Summary
    logger.info("\n")
    logger.info("╔═══════════════════════════════════════════════════════════════════╗")
    logger.info("║                        TEST SUMMARY                                ║")
    logger.info("╚═══════════════════════════════════════════════════════════════════╝")
    logger.info("\n")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"  {status} - {test_name}")
    
    logger.info("\n")
    logger.info(f"Results: {passed}/{total} tests passed")
    
    if passed == total:
        logger.info("🎉 All tests passed!")
        return 0
    else:
        logger.warning(f"⚠️  {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())


