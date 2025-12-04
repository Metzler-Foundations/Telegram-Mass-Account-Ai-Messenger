"""
Audit Integration Module - Wraps services to add automatic audit logging.

This module provides wrappers that automatically log to audit_events
without modifying existing code extensively.
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime
from functools import wraps

logger = logging.getLogger(__name__)

# Import audit logging
try:
    from accounts.account_audit_log import get_audit_log, AuditEvent, AuditEventType
    AUDIT_AVAILABLE = True
except ImportError:
    AUDIT_AVAILABLE = False
    logger.warning("Audit log not available for integration")


def with_audit_logging(event_type: 'AuditEventType'):
    """Decorator to automatically log operations to audit."""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(self, *args, **kwargs):
            if not AUDIT_AVAILABLE:
                return await func(self, *args, **kwargs)
            
            audit_log = get_audit_log()
            phone_number = kwargs.get('phone_number') or (args[0] if args else None)
            
            try:
                result = await func(self, *args, **kwargs)
                
                # Log successful operation
                if result:
                    event = AuditEvent(
                        event_id=None,
                        phone_number=str(phone_number),
                        event_type=event_type,
                        timestamp=datetime.now(),
                        success=True,
                        metadata={'result': str(result)[:200]}
                    )
                    audit_log.log_event(event)
                
                return result
            except Exception as e:
                # Log failed operation
                event = AuditEvent(
                    event_id=None,
                    phone_number=str(phone_number),
                    event_type=event_type,
                    timestamp=datetime.now(),
                    success=False,
                    error_message=str(e)[:500]
                )
                audit_log.log_event(event)
                raise
        
        @wraps(func)
        def sync_wrapper(self, *args, **kwargs):
            if not AUDIT_AVAILABLE:
                return func(self, *args, **kwargs)
            
            audit_log = get_audit_log()
            phone_number = kwargs.get('phone_number') or (args[0] if args else None)
            
            try:
                result = func(self, *args, **kwargs)
                
                # Log successful operation
                if result:
                    event = AuditEvent(
                        event_id=None,
                        phone_number=str(phone_number),
                        event_type=event_type,
                        timestamp=datetime.now(),
                        success=True
                    )
                    audit_log.log_event(event)
                
                return result
            except Exception as e:
                # Log failed operation
                event = AuditEvent(
                    event_id=None,
                    phone_number=str(phone_number),
                    event_type=event_type,
                    timestamp=datetime.now(),
                    success=False,
                    error_message=str(e)[:500]
                )
                audit_log.log_event(event)
                raise
        
        # Return appropriate wrapper based on function type
        import inspect
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


def log_sms_purchase(phone_number: str, provider: str, transaction_id: str, operator: str, cost: float):
    """Log SMS number purchase to audit."""
    if not AUDIT_AVAILABLE:
        return
    
    try:
        audit_log = get_audit_log()
        event = AuditEvent(
            event_id=None,
            phone_number=phone_number,
            event_type=AuditEventType.SMS_NUMBER_PURCHASED,
            timestamp=datetime.now(),
            sms_provider=provider,
            sms_transaction_id=transaction_id,
            sms_operator=operator,
            sms_cost=cost,
            success=True
        )
        audit_log.log_event(event)
        logger.info(f"✓ Logged SMS purchase: ${cost:.2f} from {provider}")
    except Exception as e:
        logger.error(f"Failed to log SMS purchase: {e}")


def log_proxy_assignment(phone_number: str, proxy_key: str, proxy_country: str):
    """Log proxy assignment to audit."""
    if not AUDIT_AVAILABLE:
        return
    
    try:
        audit_log = get_audit_log()
        event = AuditEvent(
            event_id=None,
            phone_number=phone_number,
            event_type=AuditEventType.PROXY_ASSIGNED,
            timestamp=datetime.now(),
            proxy_used=proxy_key,
            proxy_country=proxy_country,
            success=True
        )
        audit_log.log_event(event)
        logger.debug(f"✓ Logged proxy assignment: {proxy_key}")
    except Exception as e:
        logger.error(f"Failed to log proxy assignment: {e}")


def log_account_creation_start(phone_number: str, proxy_key: str = None, device_fingerprint: str = None):
    """Log account creation start to audit."""
    if not AUDIT_AVAILABLE:
        return
    
    try:
        audit_log = get_audit_log()
        event = AuditEvent(
            event_id=None,
            phone_number=phone_number,
            event_type=AuditEventType.ACCOUNT_CREATION_START,
            timestamp=datetime.now(),
            proxy_used=proxy_key,
            device_fingerprint=device_fingerprint,
            success=True
        )
        audit_log.log_event(event)
        logger.info(f"✓ Logged account creation start for {phone_number}")
    except Exception as e:
        logger.error(f"Failed to log account creation start: {e}")


def log_account_creation_success(phone_number: str, total_cost: float, username: str = None):
    """Log successful account creation to audit."""
    if not AUDIT_AVAILABLE:
        return
    
    try:
        audit_log = get_audit_log()
        event = AuditEvent(
            event_id=None,
            phone_number=phone_number,
            event_type=AuditEventType.ACCOUNT_CREATION_SUCCESS,
            timestamp=datetime.now(),
            username_attempted=username,
            username_success=bool(username),
            total_cost=total_cost,
            success=True
        )
        audit_log.log_event(event)
        logger.info(f"✅ Logged account creation success for {phone_number} (cost: ${total_cost:.2f})")
    except Exception as e:
        logger.error(f"Failed to log account creation success: {e}")


def log_account_creation_failure(phone_number: str, error_message: str, partial_cost: float = 0.0):
    """Log failed account creation to audit."""
    if not AUDIT_AVAILABLE:
        return
    
    try:
        audit_log = get_audit_log()
        event = AuditEvent(
            event_id=None,
            phone_number=phone_number,
            event_type=AuditEventType.ACCOUNT_CREATION_FAILURE,
            timestamp=datetime.now(),
            total_cost=partial_cost,
            success=False,
            error_message=error_message[:500]
        )
        audit_log.log_event(event)
        logger.warning(f"✓ Logged account creation failure for {phone_number}")
    except Exception as e:
        logger.error(f"Failed to log account creation failure: {e}")








