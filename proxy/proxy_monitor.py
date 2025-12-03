#!/usr/bin/env python3
"""
Proxy Monitor - REAL proxy health monitoring and testing
Actually tests proxy connections, not simulated
"""

import logging
import time
import socket
import requests
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QProgressBar,
    QMessageBox, QGroupBox, QAbstractItemView
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread
from PyQt6.QtGui import QColor, QFont

logger = logging.getLogger(__name__)


class ProxyTester(QThread):
    """Thread for REAL proxy testing with batch processing."""
    
    test_complete = pyqtSignal(str, dict)  # proxy_key, results
    all_tests_complete = pyqtSignal()
    
    def __init__(self, proxies: List[Dict], max_workers: int = 10):
        super().__init__()
        self.proxies = proxies
        self.test_url = "https://api.telegram.org"
        self.timeout = 10
        self.max_workers = max_workers
    
    def run(self):
        """Run REAL proxy tests with thread pool for better performance."""
        logger.info(f"Testing {len(self.proxies)} proxies with REAL connections...")
        
        # Use thread pool for concurrent testing
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {}
            for proxy in self.proxies:
                future = executor.submit(self.test_proxy_real, proxy)
                futures[future] = proxy
            
            # Process results as they complete
            for future in as_completed(futures):
                proxy = futures[future]
                proxy_key = f"{proxy['ip']}:{proxy['port']}"
                try:
                    results = future.result()
                    self.test_complete.emit(proxy_key, results)
                except Exception as e:
                    logger.error(f"Test failed for {proxy_key}: {e}")
                    results = {
                        'ip': proxy['ip'],
                        'port': proxy['port'],
                        'status': 'failed',
                        'error': str(e)[:50],
                        'timestamp': datetime.now().isoformat()
                    }
                    self.test_complete.emit(proxy_key, results)
        
        self.all_tests_complete.emit()
        logger.info("All proxy tests completed")
    
    def test_proxy_real(self, proxy: Dict) -> Dict:
        """Test a proxy with ACTUAL network connection."""
        proxy_key = f"{proxy['ip']}:{proxy['port']}"
        
        # Build proxy dict for requests
        proxy_url = f"http://{proxy['ip']}:{proxy['port']}"
        if proxy.get('username') and proxy.get('password'):
            proxy_url = f"http://{proxy['username']}:{proxy['password']}@{proxy['ip']}:{proxy['port']}"
        
        proxies = {
            'http': proxy_url,
            'https': proxy_url
        }
        
        results = {
            'ip': proxy['ip'],
            'port': proxy['port'],
            'status': 'testing',
            'response_time': None,
            'error': None,
            'timestamp': datetime.now().isoformat()
        }
        
        # Test 1: TCP connection
        try:
            start = time.time()
            sock = socket.create_connection((proxy['ip'], proxy['port']), timeout=self.timeout)
            sock.close()
            tcp_time = (time.time() - start) * 1000  # Convert to ms
            results['tcp_response_time'] = tcp_time
            logger.debug(f"{proxy_key} - TCP connection OK ({tcp_time:.0f}ms)")
        except Exception as e:
            results['status'] = 'failed'
            results['error'] = f"TCP connection failed: {str(e)[:50]}"
            logger.warning(f"{proxy_key} - TCP test failed: {e}")
            return results
        
        # Test 2: HTTP request through proxy
        try:
            start = time.time()
            response = requests.get(
                self.test_url,
                proxies=proxies,
                timeout=self.timeout,
                verify=False  # Skip SSL verification for testing
            )
            http_time = (time.time() - start) * 1000
            
            results['response_time'] = http_time
            results['http_status'] = response.status_code
            
            if response.status_code < 400:
                results['status'] = 'healthy'
                logger.info(f"{proxy_key} - Proxy HEALTHY ({http_time:.0f}ms)")
            else:
                results['status'] = 'degraded'
                results['error'] = f"HTTP {response.status_code}"
                logger.warning(f"{proxy_key} - HTTP error: {response.status_code}")
                
        except requests.exceptions.Timeout:
            results['status'] = 'timeout'
            results['error'] = f"Timeout ({self.timeout}s)"
            logger.warning(f"{proxy_key} - Request timeout")
            
        except requests.exceptions.ProxyError as e:
            results['status'] = 'failed'
            results['error'] = f"Proxy error: {str(e)[:50]}"
            logger.warning(f"{proxy_key} - Proxy error: {e}")
            
        except Exception as e:
            results['status'] = 'failed'
            results['error'] = f"Request failed: {str(e)[:50]}"
            logger.warning(f"{proxy_key} - Request failed: {e}")
        
        return results


class ProxyMonitorWidget(QWidget):
    """Widget for monitoring proxy health with REAL testing."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.proxies = []
        self.test_results = {}
        self.tester = None
        
        self.setup_ui()
        self.load_proxies()
    
    def setup_ui(self):
        """Setup the UI."""
        layout = QVBoxLayout(self)
        
        # Title
        title = QLabel("🌐 Proxy Health Monitor")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)
        
        # Toolbar
        toolbar = QHBoxLayout()
        
        self.test_btn = QPushButton("🧪 Test All Proxies")
        self.test_btn.clicked.connect(self.test_all_proxies)
        self.test_btn.setObjectName("primary")
        toolbar.addWidget(self.test_btn)
        
        self.test_selected_btn = QPushButton("Test Selected")
        self.test_selected_btn.clicked.connect(self.test_selected)
        toolbar.addWidget(self.test_selected_btn)
        
        self.remove_failed_btn = QPushButton("🗑️ Remove Failed")
        self.remove_failed_btn.clicked.connect(self.remove_failed_proxies)
        self.remove_failed_btn.setObjectName("danger")
        toolbar.addWidget(self.remove_failed_btn)
        
        self.add_proxy_btn = QPushButton("➕ Add Proxy")
        self.add_proxy_btn.clicked.connect(self.add_proxy)
        toolbar.addWidget(self.add_proxy_btn)
        
        toolbar.addStretch()
        
        self.auto_test_check = QCheckBox("Auto-test every 5 min")
        self.auto_test_check.toggled.connect(self.toggle_auto_test)
        toolbar.addWidget(self.auto_test_check)
        
        layout.addLayout(toolbar)
        
        # Status
        self.status_label = QLabel()
        layout.addWidget(self.status_label)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # Proxy table
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "Proxy", "Status", "Response Time", "Last Tested",
            "Success Rate", "Total Tests", "Actions"
        ])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        layout.addWidget(self.table)
        
        # Auto-test timer
        self.auto_test_timer = QTimer(self)
        self.auto_test_timer.timeout.connect(self.test_all_proxies)
    
    def load_proxies(self):
        """Load proxies from REAL configuration with optimization."""
        try:
            import json
            from pathlib import Path
            from PyQt6.QtWidgets import QMessageBox
            
            config_file = Path("config.json")
            if config_file.exists():
                with open(config_file, 'r') as f:
                    config = json.load(f)
                
                # Get proxy list from config
                proxy_list = config.get('proxies', {}).get('proxy_list', [])
                
                # Warn if too many proxies
                total_proxies = len(proxy_list)
                if total_proxies > 50000:
                    QMessageBox.warning(
                        self,
                        "Large Proxy List",
                        f"Config contains {total_proxies:,} proxies.\n\n"
                        f"Loading only first 10,000 for performance.\n"
                        f"Use Proxy Pool Manager for full dataset."
                    )
                    proxy_list = proxy_list[:10000]
                elif total_proxies > 10000:
                    # Load only first 10,000
                    proxy_list = proxy_list[:10000]
                    logger.warning(f"Loaded only first 10,000 of {total_proxies} proxies")
                
                self.proxies = []
                for proxy_str in proxy_list:
                    parts = proxy_str.split(':')
                    if len(parts) >= 2:
                        proxy = {
                            'ip': parts[0],
                            'port': int(parts[1]),
                            'username': parts[2] if len(parts) > 2 else None,
                            'password': parts[3] if len(parts) > 3 else None
                        }
                        self.proxies.append(proxy)
                
                logger.info(f"Loaded {len(self.proxies)} REAL proxies from config")
            
            self.refresh_table()
            self.update_status()
            
        except Exception as e:
            logger.error(f"Failed to load proxies: {e}")
    
    def refresh_table(self):
        """Refresh proxy table with REAL data (optimized)."""
        # Disable updates for better performance
        self.table.setUpdatesEnabled(False)
        self.table.setSortingEnabled(False)
        
        self.table.setRowCount(len(self.proxies))
        
        for row, proxy in enumerate(self.proxies):
            proxy_key = f"{proxy['ip']}:{proxy['port']}"
            
            # Proxy address
            self.table.setItem(row, 0, QTableWidgetItem(proxy_key))
            
            # Status
            if proxy_key in self.test_results:
                result = self.test_results[proxy_key]
                status = result['status']
                
                status_item = QTableWidgetItem(status.upper())
                if status == 'healthy':
                    status_item.setForeground(QColor('#23a559'))
                elif status == 'degraded':
                    status_item.setForeground(QColor('#faa61a'))
                elif status == 'timeout':
                    status_item.setForeground(QColor('#faa61a'))
                else:
                    status_item.setForeground(QColor('#f23f42'))
                
                self.table.setItem(row, 1, status_item)
                
                # Response time
                if result.get('response_time'):
                    time_item = QTableWidgetItem(f"{result['response_time']:.0f} ms")
                    if result['response_time'] < 500:
                        time_item.setForeground(QColor('#23a559'))
                    elif result['response_time'] < 2000:
                        time_item.setForeground(QColor('#faa61a'))
                    else:
                        time_item.setForeground(QColor('#f23f42'))
                    self.table.setItem(row, 2, time_item)
                else:
                    self.table.setItem(row, 2, QTableWidgetItem("N/A"))
                
                # Last tested
                if result.get('timestamp'):
                    tested_dt = datetime.fromisoformat(result['timestamp'])
                    time_ago = datetime.now() - tested_dt
                    if time_ago.total_seconds() < 60:
                        ago_str = "Just now"
                    elif time_ago.total_seconds() < 3600:
                        ago_str = f"{int(time_ago.total_seconds() / 60)} min ago"
                    else:
                        ago_str = f"{int(time_ago.total_seconds() / 3600)} hours ago"
                    self.table.setItem(row, 3, QTableWidgetItem(ago_str))
            else:
                self.table.setItem(row, 1, QTableWidgetItem("NOT TESTED"))
                self.table.setItem(row, 2, QTableWidgetItem("-"))
                self.table.setItem(row, 3, QTableWidgetItem("Never"))
        
        # Re-enable updates
        self.table.setUpdatesEnabled(True)
    
    def test_all_proxies(self):
        """Test all proxies with REAL network requests."""
        if not self.proxies:
            QMessageBox.warning(
                self,
                "No Proxies",
                "No proxies configured.\n\nAdd proxies in Settings to test them."
            )
            return
        
        if self.tester and self.tester.isRunning():
            QMessageBox.warning(self, "Test Running", "Proxy test already in progress")
            return
        
        logger.info(f"Starting REAL proxy tests for {len(self.proxies)} proxies...")
        
        self.test_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, len(self.proxies))
        self.progress_bar.setValue(0)
        
        self.status_label.setText(f"🧪 Testing {len(self.proxies)} proxies...")
        
        # Start tester thread
        self.tester = ProxyTester(self.proxies)
        self.tester.test_complete.connect(self.on_test_complete)
        self.tester.all_tests_complete.connect(self.on_all_tests_complete)
        self.tester.start()
    
    def test_selected(self):
        """Test selected proxy."""
        selected = self.table.selectedItems()
        if not selected:
            QMessageBox.warning(self, "No Selection", "Select a proxy to test")
            return
        
        row = self.table.currentRow()
        proxy = self.proxies[row]
        
        logger.info(f"Testing single proxy: {proxy['ip']}:{proxy['port']}")
        
        # Run test in thread
        tester = ProxyTester([proxy])
        tester.test_complete.connect(self.on_test_complete)
        tester.all_tests_complete.connect(lambda: self.status_label.setText("✅ Test complete"))
        tester.start()
    
    def on_test_complete(self, proxy_key: str, results: Dict):
        """Handle REAL test result."""
        self.test_results[proxy_key] = results
        
        # Update progress
        current = self.progress_bar.value()
        self.progress_bar.setValue(current + 1)
        
        # Update status
        status = results['status']
        response_time = results.get('response_time', 0)
        
        if status == 'healthy':
            self.status_label.setText(f"✅ {proxy_key} - Healthy ({response_time:.0f}ms)")
        elif status == 'degraded':
            self.status_label.setText(f"⚠️ {proxy_key} - Degraded ({response_time:.0f}ms)")
        elif status == 'timeout':
            self.status_label.setText(f"⏱️ {proxy_key} - Timeout")
        else:
            error = results.get('error', 'Unknown')
            self.status_label.setText(f"❌ {proxy_key} - Failed: {error}")
        
        self.refresh_table()
    
    def on_all_tests_complete(self):
        """Handle completion of all tests."""
        self.test_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        
        # Count results
        healthy = sum(1 for r in self.test_results.values() if r['status'] == 'healthy')
        failed = sum(1 for r in self.test_results.values() if r['status'] == 'failed')
        degraded = sum(1 for r in self.test_results.values() if r['status'] in ['degraded', 'timeout'])
        
        self.status_label.setText(
            f"✅ Test complete: {healthy} healthy, {degraded} degraded, {failed} failed"
        )
        
        logger.info(f"Proxy test results: {healthy} healthy, {degraded} degraded, {failed} failed")
    
    def remove_failed_proxies(self):
        """Remove proxies that failed testing."""
        failed_count = sum(
            1 for r in self.test_results.values() 
            if r['status'] == 'failed'
        )
        
        if failed_count == 0:
            QMessageBox.information(self, "No Failed Proxies", "No failed proxies to remove")
            return
        
        reply = QMessageBox.question(
            self,
            "Confirm Remove",
            f"Remove {failed_count} failed proxies?\n\nThis will update your configuration."
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # Remove failed proxies
            self.proxies = [
                p for p in self.proxies
                if f"{p['ip']}:{p['port']}" not in self.test_results
                or self.test_results[f"{p['ip']}:{p['port']}"]["status"] != 'failed'
            ]
            
            self.save_proxies()
            self.refresh_table()
            self.update_status()
            
            QMessageBox.information(
                self,
                "Success",
                f"Removed {failed_count} failed proxies"
            )
    
    def add_proxy(self):
        """Add a new proxy."""
        from PyQt6.QtWidgets import QInputDialog
        
        proxy_str, ok = QInputDialog.getText(
            self,
            "Add Proxy",
            "Enter proxy (format: ip:port or ip:port:username:password):",
            text="1.2.3.4:8080"
        )
        
        if ok and proxy_str:
            parts = proxy_str.split(':')
            if len(parts) >= 2:
                try:
                    proxy = {
                        'ip': parts[0],
                        'port': int(parts[1]),
                        'username': parts[2] if len(parts) > 2 else None,
                        'password': parts[3] if len(parts) > 3 else None
                    }
                    
                    self.proxies.append(proxy)
                    self.save_proxies()
                    self.refresh_table()
                    self.update_status()
                    
                    QMessageBox.information(self, "Success", "Proxy added successfully")
                    
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Invalid proxy format: {e}")
            else:
                QMessageBox.warning(
                    self,
                    "Invalid Format",
                    "Proxy format should be: ip:port or ip:port:username:password"
                )
    
    def save_proxies(self):
        """Save proxies to REAL configuration file."""
        try:
            import json
            from pathlib import Path
            
            config_file = Path("config.json")
            
            # Load existing config
            if config_file.exists():
                with open(config_file, 'r') as f:
                    config = json.load(f)
            else:
                config = {}
            
            # Update proxy list
            if 'proxies' not in config:
                config['proxies'] = {}
            
            # Convert proxies to strings
            proxy_list = []
            for proxy in self.proxies:
                proxy_str = f"{proxy['ip']}:{proxy['port']}"
                if proxy.get('username'):
                    proxy_str += f":{proxy['username']}:{proxy.get('password', '')}"
                proxy_list.append(proxy_str)
            
            config['proxies']['proxy_list'] = proxy_list
            
            # Save config
            with open(config_file, 'w') as f:
                json.dump(config, f, indent=2)
            
            logger.info(f"Saved {len(self.proxies)} proxies to config")
            
        except Exception as e:
            logger.error(f"Failed to save proxies: {e}")
            QMessageBox.critical(self, "Error", f"Failed to save proxies: {e}")
    
    def update_status(self):
        """Update status label."""
        if not self.proxies:
            self.status_label.setText("⚠️ No proxies configured")
            return
        
        healthy = sum(
            1 for r in self.test_results.values() 
            if r.get('status') == 'healthy'
        )
        
        total = len(self.proxies)
        tested = len(self.test_results)
        
        if tested == 0:
            self.status_label.setText(
                f"📋 {total} proxies configured. Click 'Test All' to check health."
            )
        else:
            self.status_label.setText(
                f"📊 {healthy}/{tested} proxies healthy"
            )
    
    def toggle_auto_test(self, enabled: bool):
        """Toggle automatic testing."""
        if enabled:
            self.auto_test_timer.start(300000)  # 5 minutes
            logger.info("Auto-test enabled (every 5 minutes)")
            self.status_label.setText("🔄 Auto-test enabled (every 5 minutes)")
        else:
            self.auto_test_timer.stop()
            logger.info("Auto-test disabled")
            self.update_status()

