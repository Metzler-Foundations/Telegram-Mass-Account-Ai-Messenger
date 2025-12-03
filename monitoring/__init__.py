"""
Performance and monitoring module.
"""
# Lazy imports to avoid circular dependencies
def __getattr__(name):
    if name == 'PerformanceMonitor':
        from .performance_monitor import PerformanceMonitor
        return PerformanceMonitor
    elif name == 'get_resilience_manager':
        from .performance_monitor import get_resilience_manager
        return get_resilience_manager
    elif name == 'get_features_manager':
        from .advanced_features_manager import get_features_manager
        return get_features_manager
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    'PerformanceMonitor',
    'get_resilience_manager',
    'get_features_manager',
]

