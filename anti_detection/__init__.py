"""
Anti-detection systems module.
"""
# Lazy imports to avoid circular dependencies
def __getattr__(name):
    if name == 'AntiDetectionSystem':
        from .anti_detection_system import AntiDetectionSystem
        return AntiDetectionSystem
    elif name in ('ShadowBanDetector', 'ShadowBanStatus'):
        from . import shadowban_detector
        return getattr(shadowban_detector, name)
    elif name == 'LocationSpoofer':
        from .location_spoofer import LocationSpoofer
        return LocationSpoofer
    elif name == 'TimezoneDetector':
        from .timezone_detector import TimezoneDetector
        return TimezoneDetector
    elif name == 'TimingOptimizer':
        from .timing_optimizer import TimingOptimizer
        return TimingOptimizer
    elif name == 'AdvancedCloningSystem':
        from .advanced_cloning_system import AdvancedCloningSystem
        return AdvancedCloningSystem
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    'AntiDetectionSystem',
    'ShadowBanDetector',
    'ShadowBanStatus',
    'LocationSpoofer',
    'TimezoneDetector',
    'TimingOptimizer',
    'AdvancedCloningSystem',
]

