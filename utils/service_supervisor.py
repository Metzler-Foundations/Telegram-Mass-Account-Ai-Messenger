#!/usr/bin/env python3
"""Service supervisor - Auto-restart background services on crash."""

import asyncio
import logging
from typing import Dict, Callable, Awaitable, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class ServiceSupervisor:
    """Supervises and auto-restarts services."""
    
    def __init__(self, max_restarts: int = 5, restart_window: int = 300):
        self.services: Dict[str, Dict] = {}
        self.max_restarts = max_restarts
        self.restart_window = restart_window  # seconds
    
    def register_service(self, name: str, start_func: Callable[[], Awaitable[None]]):
        """Register a service for supervision."""
        self.services[name] = {
            'start_func': start_func,
            'task': None,
            'restarts': [],
            'running': False
        }
        logger.info(f"Registered service: {name}")
    
    async def start_service(self, name: str):
        """Start a supervised service."""
        if name not in self.services:
            logger.error(f"Unknown service: {name}")
            return
        
        service = self.services[name]
        
        if service['running']:
            logger.warning(f"Service already running: {name}")
            return
        
        logger.info(f"Starting service: {name}")
        service['task'] = asyncio.create_task(self._run_supervised(name))
        service['running'] = True
    
    async def _run_supervised(self, name: str):
        """Run service with supervision."""
        service = self.services[name]
        
        while True:
            try:
                await service['start_func']()
            except Exception as e:
                logger.error(f"Service {name} crashed: {e}")
                
                # Check restart limit
                now = datetime.now().timestamp()
                service['restarts'] = [
                    ts for ts in service['restarts']
                    if now - ts < self.restart_window
                ]
                
                if len(service['restarts']) >= self.max_restarts:
                    logger.critical(f"Service {name} exceeded restart limit, giving up")
                    service['running'] = False
                    break
                
                service['restarts'].append(now)
                delay = min(2 ** len(service['restarts']), 60)
                
                logger.info(f"Restarting {name} in {delay}s...")
                await asyncio.sleep(delay)
    
    async def stop_service(self, name: str):
        """Stop a supervised service."""
        if name not in self.services:
            return
        
        service = self.services[name]
        if service['task']:
            service['task'].cancel()
            service['running'] = False
        
        logger.info(f"Stopped service: {name}")
    
    def is_running(self, name: str) -> bool:
        """Check if service is running."""
        return self.services.get(name, {}).get('running', False)


_supervisor = None

def get_supervisor():
    global _supervisor
    if _supervisor is None:
        _supervisor = ServiceSupervisor()
    return _supervisor

