#!/usr/bin/env python3
"""
Health Check System - Monitoring and liveness probes.

Features:
- Liveness probe (is service running?)
- Readiness probe (is service ready to accept requests?)
- Dependency health checks
- Detailed status reporting
- HTTP endpoint support
"""

import logging
import time
import threading
from typing import Dict, List, Callable, Optional, Any
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Health status levels."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class HealthCheck:
    """Individual health check result."""
    name: str
    status: HealthStatus
    message: str
    checked_at: datetime
    response_time_ms: float = 0.0
    details: Optional[Dict[str, Any]] = None


class HealthCheckManager:
    """
    Manages application health checks.
    
    Provides liveness and readiness probes for monitoring.
    """
    
    def __init__(self):
        """Initialize health check manager."""
        self.checks: Dict[str, Callable] = {}
        self.last_results: Dict[str, HealthCheck] = {}
        self.lock = threading.Lock()
        
        # Statistics
        self.stats = {
            'total_checks': 0,
            'healthy_checks': 0,
            'unhealthy_checks': 0,
            'degraded_checks': 0
        }
    
    def register_check(self, name: str, check_func: Callable) -> None:
        """
        Register a health check.
        
        Args:
            name: Check name
            check_func: Function that returns (status, message, details)
        """
        with self.lock:
            self.checks[name] = check_func
            logger.debug(f"Registered health check: {name}")
    
    def check_database(self) -> tuple:
        """Check database connectivity."""
        try:
            from database.connection_pool import get_pool
            
            pool = get_pool('members.db', min_connections=1, max_connections=2)
            
            with pool.get_connection() as conn:
                result = conn.execute("SELECT 1").fetchone()
                
                if result:
                    stats = pool.get_stats()
                    return (
                        HealthStatus.HEALTHY,
                        "Database accessible",
                        stats
                    )
            
            return (HealthStatus.UNHEALTHY, "Database query failed", None)
            
        except Exception as e:
            return (HealthStatus.UNHEALTHY, f"Database error: {e}", None)
    
    def check_memory(self) -> tuple:
        """Check memory usage."""
        try:
            import psutil
            
            process = psutil.Process()
            memory_mb = process.memory_info().rss / 1024 / 1024
            percent = process.memory_percent()
            
            if memory_mb > 1500:  # 1.5GB
                status = HealthStatus.UNHEALTHY
                message = f"Memory usage critical: {memory_mb:.1f}MB"
            elif memory_mb > 1000:  # 1GB
                status = HealthStatus.DEGRADED
                message = f"Memory usage high: {memory_mb:.1f}MB"
            else:
                status = HealthStatus.HEALTHY
                message = f"Memory usage normal: {memory_mb:.1f}MB"
            
            return (status, message, {'memory_mb': memory_mb, 'percent': percent})
            
        except Exception as e:
            return (HealthStatus.UNKNOWN, f"Memory check failed: {e}", None)
    
    def check_disk_space(self) -> tuple:
        """Check available disk space."""
        try:
            import psutil
            from pathlib import Path
            
            # Check disk for database directory
            db_path = Path('.')
            disk = psutil.disk_usage(str(db_path))
            
            free_gb = disk.free / (1024 ** 3)
            percent_used = disk.percent
            
            if free_gb < 1:  # Less than 1GB free
                status = HealthStatus.UNHEALTHY
                message = f"Disk space critical: {free_gb:.2f}GB free"
            elif free_gb < 5:  # Less than 5GB free
                status = HealthStatus.DEGRADED
                message = f"Disk space low: {free_gb:.2f}GB free"
            else:
                status = HealthStatus.HEALTHY
                message = f"Disk space adequate: {free_gb:.2f}GB free"
            
            return (status, message, {
                'free_gb': free_gb,
                'used_percent': percent_used
            })
            
        except Exception as e:
            return (HealthStatus.UNKNOWN, f"Disk check failed: {e}", None)
    
    def run_checks(self) -> Dict[str, HealthCheck]:
        """
        Run all registered health checks.
        
        Returns:
            Dictionary of check results
        """
        results = {}
        
        with self.lock:
            checks_to_run = self.checks.copy()
        
        for name, check_func in checks_to_run.items():
            start_time = time.time()
            
            try:
                status, message, details = check_func()
                response_time = (time.time() - start_time) * 1000  # ms
                
                result = HealthCheck(
                    name=name,
                    status=status,
                    message=message,
                    checked_at=datetime.now(),
                    response_time_ms=response_time,
                    details=details
                )
                
                results[name] = result
                
                # Update stats
                self.stats['total_checks'] += 1
                if status == HealthStatus.HEALTHY:
                    self.stats['healthy_checks'] += 1
                elif status == HealthStatus.UNHEALTHY:
                    self.stats['unhealthy_checks'] += 1
                elif status == HealthStatus.DEGRADED:
                    self.stats['degraded_checks'] += 1
                
            except Exception as e:
                logger.error(f"Health check {name} failed: {e}")
                results[name] = HealthCheck(
                    name=name,
                    status=HealthStatus.UNKNOWN,
                    message=f"Check error: {e}",
                    checked_at=datetime.now()
                )
        
        with self.lock:
            self.last_results = results
        
        return results
    
    def is_healthy(self) -> bool:
        """
        Check if application is healthy.
        
        Returns:
            True if all checks are healthy or degraded
        """
        results = self.run_checks()
        
        for check in results.values():
            if check.status == HealthStatus.UNHEALTHY:
                return False
        
        return len(results) > 0
    
    def is_ready(self) -> bool:
        """
        Check if application is ready to accept requests.
        
        Returns:
            True if all critical checks are healthy
        """
        results = self.run_checks()
        
        # Critical checks that must be healthy
        critical_checks = ['database']
        
        for check_name in critical_checks:
            if check_name in results:
                if results[check_name].status != HealthStatus.HEALTHY:
                    return False
        
        return True
    
    def get_status_dict(self) -> Dict:
        """
        Get health status as dictionary.
        
        Returns:
            Status dictionary (suitable for JSON API response)
        """
        results = self.run_checks()
        
        overall_status = HealthStatus.HEALTHY
        for check in results.values():
            if check.status == HealthStatus.UNHEALTHY:
                overall_status = HealthStatus.UNHEALTHY
                break
            elif check.status == HealthStatus.DEGRADED:
                overall_status = HealthStatus.DEGRADED
        
        return {
            'status': overall_status.value,
            'timestamp': datetime.now().isoformat(),
            'checks': {
                name: {
                    'status': check.status.value,
                    'message': check.message,
                    'response_time_ms': check.response_time_ms,
                    'details': check.details
                }
                for name, check in results.items()
            },
            'statistics': self.stats
        }


# Global instance
_health_manager: Optional[HealthCheckManager] = None


def get_health_manager() -> HealthCheckManager:
    """Get global health check manager."""
    global _health_manager
    if _health_manager is None:
        _health_manager = HealthCheckManager()
        
        # Register default checks
        _health_manager.register_check('database', _health_manager.check_database)
        _health_manager.register_check('memory', _health_manager.check_memory)
        _health_manager.register_check('disk', _health_manager.check_disk_space)
    
    return _health_manager


# HTTP endpoint support
def create_health_endpoint():
    """
    Create HTTP health check endpoint.
    
    Returns a simple HTTP server for /health endpoint.
    """
    from http.server import HTTPServer, BaseHTTPRequestHandler
    import json
    
    class HealthHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == '/health':
                manager = get_health_manager()
                status = manager.get_status_dict()
                
                # Determine HTTP status code
                if status['status'] == 'healthy':
                    http_code = 200
                elif status['status'] == 'degraded':
                    http_code = 200  # Still operational
                else:
                    http_code = 503  # Service unavailable
                
                self.send_response(http_code)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(status, indent=2).encode())
                
            elif self.path == '/ready':
                manager = get_health_manager()
                ready = manager.is_ready()
                
                self.send_response(200 if ready else 503)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'ready': ready}).encode())
                
            else:
                self.send_response(404)
                self.end_headers()
        
        def log_message(self, format, *args):
            # Suppress HTTP logs (use app logger instead)
            pass
    
    return HTTPServer(('0.0.0.0', 8080), HealthHandler)


if __name__ == "__main__":
    # Test health checks
    manager = get_health_manager()
    
    print("Running health checks...")
    status = manager.get_status_dict()
    
    print(f"\nOverall Status: {status['status'].upper()}")
    print(f"Timestamp: {status['timestamp']}")
    print("\nIndividual Checks:")
    for name, check in status['checks'].items():
        print(f"  {name}: {check['status']} - {check['message']}")



