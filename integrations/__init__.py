"""
External integrations module.
"""
# Lazy imports to avoid circular dependencies
def __getattr__(name):
    if name == 'APIKeyManager':
        from .api_key_manager import APIKeyManager
        return APIKeyManager
    elif name == 'VoiceService':
        from .voice_service import VoiceService
        return VoiceService
    elif name == 'MediaProcessor':
        from .media_processor import MediaProcessor
        return MediaProcessor
    elif name in ('NotificationManager', 'KeyboardShortcuts'):
        from . import notification_system
        return getattr(notification_system, name)
    elif name == 'DataExportDialog':
        from .data_export import DataExportDialog
        return DataExportDialog
    elif name == 'ExportManager':
        from .export_manager import ExportManager
        return ExportManager
    elif name == 'IntegrationConnector':
        from .integration_connector import IntegrationConnector
        return IntegrationConnector
    elif name == 'AutoIntegrator':
        from .auto_integrator import AutoIntegrator
        return AutoIntegrator
    elif name == 'SystemIntegration':
        from .system_integration import SystemIntegration
        return SystemIntegration
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    'APIKeyManager',
    'VoiceService',
    'MediaProcessor',
    'NotificationManager',
    'KeyboardShortcuts',
    'DataExportDialog',
    'ExportManager',
    'IntegrationConnector',
    'AutoIntegrator',
    'SystemIntegration',
]

