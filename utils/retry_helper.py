#!/usr/bin/env python3
"""
Retry Helper - Automatic retry logic with exponential backoff
Provides user-friendly retry mechanisms for failed operations
"""

import asyncio
import logging
import time
import random
from typing import Callable, Any, Optional, List, Dict
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class RetryStrategy(Enum):
    """Retry strategy types."""
    EXPONENTIAL = "exponential"  # 1s, 2s, 4s, 8s...
    LINEAR = "linear"            # 1s, 2s, 3s, 4s...
    FIXED = "fixed"              # 1s, 1s, 1s, 1s...
    FIBONACCI = "fibonacci"       # 1s, 1s, 2s, 3s, 5s, 8s...


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    max_attempts: int = 3
    base_delay: float = 1.0  # seconds
    max_delay: float = 60.0  # seconds
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL
    backoff_multiplier: float = 2.0
    jitter: bool = True  # Add random jitter to prevent thundering herd
    retry_on_exceptions: Optional[List[type]] = None  # Specific exceptions to retry
    give_up_on_exceptions: Optional[List[type]] = None  # Exceptions to immediately fail


class RetryHelper:
    """Provides retry logic with exponential backoff."""
    
    @staticmethod
    def calculate_delay(attempt: int, config: RetryConfig) -> float:
        """
        Calculate delay for retry attempt.
        
        Args:
            attempt: Current attempt number (0-indexed)
            config: Retry configuration
            
        Returns:
            Delay in seconds
        """
        if config.strategy == RetryStrategy.EXPONENTIAL:
            delay = config.base_delay * (config.backoff_multiplier ** attempt)
        elif config.strategy == RetryStrategy.LINEAR:
            delay = config.base_delay * (attempt + 1)
        elif config.strategy == RetryStrategy.FIBONACCI:
            # Generate Fibonacci sequence
            a, b = 1, 1
            for _ in range(attempt):
                a, b = b, a + b
            delay = config.base_delay * a
        else:  # FIXED
            delay = config.base_delay
        
        # Cap at max delay
        delay = min(delay, config.max_delay)
        
        # Add jitter to prevent thundering herd
        if config.jitter:
            jitter_amount = delay * 0.1  # +/- 10%
            delay += random.uniform(-jitter_amount, jitter_amount)
        
        return max(0.1, delay)  # Minimum 0.1s
    
    @staticmethod
    def should_retry(exception: Exception, config: RetryConfig) -> bool:
        """
        Determine if exception should trigger retry.
        
        Args:
            exception: The exception that occurred
            config: Retry configuration
            
        Returns:
            True if should retry, False otherwise
        """
        # Check if we should immediately give up
        if config.give_up_on_exceptions:
            for exc_type in config.give_up_on_exceptions:
                if isinstance(exception, exc_type):
                    logger.debug(f"Not retrying: exception type {exc_type.__name__} in give_up list")
                    return False
        
        # Check if we should retry specific exceptions only
        if config.retry_on_exceptions:
            for exc_type in config.retry_on_exceptions:
                if isinstance(exception, exc_type):
                    return True
            logger.debug(f"Not retrying: exception type {type(exception).__name__} not in retry list")
            return False
        
        # Default: retry all exceptions
        return True
    
    @staticmethod
    async def retry_async(
        func: Callable,
        config: Optional[RetryConfig] = None,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
        context: str = ""
    ) -> Any:
        """
        Retry an async function with exponential backoff.
        
        Args:
            func: Async function to retry
            config: Retry configuration
            progress_callback: Called with (attempt, max_attempts, message)
            context: Context string for logging/progress
            
        Returns:
            Function result
            
        Raises:
            Last exception if all retries exhausted
        """
        if config is None:
            config = RetryConfig()
        
        last_exception = None
        
        for attempt in range(config.max_attempts):
            try:
                if progress_callback and attempt > 0:
                    progress_callback(
                        attempt + 1,
                        config.max_attempts,
                        f"🔄 Retry attempt {attempt + 1}/{config.max_attempts}..."
                    )
                
                result = await func()
                
                if attempt > 0:
                    logger.info(f"✅ {context} succeeded on attempt {attempt + 1}")
                
                return result
                
            except Exception as e:
                last_exception = e
                
                # Check if we should retry
                if not RetryHelper.should_retry(e, config):
                    logger.error(f"❌ {context} failed with non-retryable error: {e}")
                    raise
                
                # Check if this was the last attempt
                if attempt == config.max_attempts - 1:
                    logger.error(f"❌ {context} failed after {config.max_attempts} attempts: {e}")
                    if progress_callback:
                        progress_callback(
                            config.max_attempts,
                            config.max_attempts,
                            f"❌ Failed after {config.max_attempts} attempts"
                        )
                    raise
                
                # Calculate delay and wait
                delay = RetryHelper.calculate_delay(attempt, config)
                logger.warning(
                    f"⚠️ {context} attempt {attempt + 1} failed: {e}. "
                    f"Retrying in {delay:.1f}s..."
                )
                
                if progress_callback:
                    progress_callback(
                        attempt + 1,
                        config.max_attempts,
                        f"⏳ Waiting {delay:.0f}s before retry..."
                    )
                
                await asyncio.sleep(delay)
        
        # Should never reach here, but just in case
        if last_exception:
            raise last_exception
    
    @staticmethod
    def retry_sync(
        func: Callable,
        config: Optional[RetryConfig] = None,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
        context: str = ""
    ) -> Any:
        """
        Retry a synchronous function with exponential backoff.
        
        Args:
            func: Synchronous function to retry
            config: Retry configuration
            progress_callback: Called with (attempt, max_attempts, message)
            context: Context string for logging/progress
            
        Returns:
            Function result
            
        Raises:
            Last exception if all retries exhausted
        """
        if config is None:
            config = RetryConfig()
        
        last_exception = None
        
        for attempt in range(config.max_attempts):
            try:
                if progress_callback and attempt > 0:
                    progress_callback(
                        attempt + 1,
                        config.max_attempts,
                        f"🔄 Retry attempt {attempt + 1}/{config.max_attempts}..."
                    )
                
                result = func()
                
                if attempt > 0:
                    logger.info(f"✅ {context} succeeded on attempt {attempt + 1}")
                
                return result
                
            except Exception as e:
                last_exception = e
                
                # Check if we should retry
                if not RetryHelper.should_retry(e, config):
                    logger.error(f"❌ {context} failed with non-retryable error: {e}")
                    raise
                
                # Check if this was the last attempt
                if attempt == config.max_attempts - 1:
                    logger.error(f"❌ {context} failed after {config.max_attempts} attempts: {e}")
                    if progress_callback:
                        progress_callback(
                            config.max_attempts,
                            config.max_attempts,
                            f"❌ Failed after {config.max_attempts} attempts"
                        )
                    raise
                
                # Calculate delay and wait
                delay = RetryHelper.calculate_delay(attempt, config)
                logger.warning(
                    f"⚠️ {context} attempt {attempt + 1} failed: {e}. "
                    f"Retrying in {delay:.1f}s..."
                )
                
                if progress_callback:
                    progress_callback(
                        attempt + 1,
                        config.max_attempts,
                        f"⏳ Waiting {delay:.0f}s before retry..."
                    )
                
                time.sleep(delay)
        
        # Should never reach here, but just in case
        if last_exception:
            raise last_exception


class OperationRecovery:
    """Manages recovery of interrupted operations."""
    
    def __init__(self, state_file: str = ".operation_state.json"):
        self.state_file = state_file
        self.state: Dict[str, Any] = {}
        self.load_state()
    
    def load_state(self):
        """Load saved operation state."""
        try:
            import json
            from pathlib import Path
            
            if Path(self.state_file).exists():
                with open(self.state_file, 'r') as f:
                    self.state = json.load(f)
                logger.info(f"Loaded operation state: {len(self.state)} operations")
        except Exception as e:
            logger.warning(f"Failed to load operation state: {e}")
            self.state = {}
    
    def save_state(self):
        """Save current operation state."""
        try:
            import json
            with open(self.state_file, 'w') as f:
                json.dump(self.state, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save operation state: {e}")
    
    def save_checkpoint(self, operation_id: str, checkpoint_data: Dict[str, Any]):
        """Save a checkpoint for resumable operation."""
        self.state[operation_id] = {
            "checkpoint_data": checkpoint_data,
            "timestamp": time.time(),
            "operation_id": operation_id
        }
        self.save_state()
        logger.debug(f"Saved checkpoint for operation: {operation_id}")
    
    def get_checkpoint(self, operation_id: str) -> Optional[Dict[str, Any]]:
        """Get checkpoint data for operation."""
        if operation_id in self.state:
            return self.state[operation_id]["checkpoint_data"]
        return None
    
    def clear_checkpoint(self, operation_id: str):
        """Clear checkpoint for completed operation."""
        if operation_id in self.state:
            del self.state[operation_id]
            self.save_state()
            logger.debug(f"Cleared checkpoint for operation: {operation_id}")
    
    def list_incomplete_operations(self) -> List[Dict[str, Any]]:
        """List all incomplete operations that can be resumed."""
        result = []
        current_time = time.time()
        
        for op_id, data in self.state.items():
            age_hours = (current_time - data["timestamp"]) / 3600
            result.append({
                "operation_id": op_id,
                "timestamp": data["timestamp"],
                "age_hours": age_hours,
                "data": data["checkpoint_data"]
            })
        
        return result


# Convenience functions
async def retry_async(
    func: Callable,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    context: str = ""
) -> Any:
    """Simplified async retry with defaults."""
    config = RetryConfig(max_attempts=max_attempts, base_delay=base_delay)
    return await RetryHelper.retry_async(func, config, context=context)


def retry_sync(
    func: Callable,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    context: str = ""
) -> Any:
    """Simplified sync retry with defaults."""
    config = RetryConfig(max_attempts=max_attempts, base_delay=base_delay)
    return RetryHelper.retry_sync(func, config, context=context)

