"""
Utilities and helpers module.
"""
# Lazy imports to avoid circular dependencies
def __getattr__(name):
    if name == 'RetryHelper':
        from .retry_helper import RetryHelper
        return RetryHelper
    elif name in ('LazyValue', 'LazyProperty', 'LazyDict'):
        from . import lazy_loader
        return getattr(lazy_loader, name)
    elif name == 'ObjectPool':
        from .object_pool import ObjectPool
        return ObjectPool
    elif name == 'BatchOptimizer':
        from .batch_optimizer import BatchOptimizer
        return BatchOptimizer
    elif name == 'MemoryOptimizer':
        from .memory_optimizer import MemoryOptimizer
        return MemoryOptimizer
    elif name == 'ProgressTracker':
        from .progress_tracker import ProgressTracker
        return ProgressTracker
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    'RetryHelper',
    'LazyValue',
    'LazyProperty',
    'LazyDict',
    'ObjectPool',
    'BatchOptimizer',
    'MemoryOptimizer',
    'ProgressTracker',
]

