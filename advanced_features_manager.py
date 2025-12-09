"""Top-level import shim for advanced features manager.

This keeps backward compatibility for test suite and integrations that
expect `advanced_features_manager` to be importable from the project root.
"""

from monitoring.advanced_features_manager import AdvancedFeaturesManager, get_features_manager

__all__ = ["AdvancedFeaturesManager", "get_features_manager"]
