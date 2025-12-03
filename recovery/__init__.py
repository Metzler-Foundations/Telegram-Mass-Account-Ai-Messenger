"""
Recovery and backup systems module.
"""
# Lazy imports to avoid circular dependencies
def __getattr__(name):
    if name == 'CrashRecovery':
        from .crash_recovery import CrashRecovery
        return CrashRecovery
    elif name in ('RecoveryProtocol', 'RecoveryStage'):
        from . import recovery_protocol
        return getattr(recovery_protocol, name)
    elif name in ('BackupCreator', 'BackupRestorer', 'BackupManagerDialog'):
        from . import backup_restore
        return getattr(backup_restore, name)
    elif name == 'ResumeManager':
        from .resume_manager import ResumeManager
        return ResumeManager
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    'CrashRecovery',
    'RecoveryProtocol',
    'RecoveryStage',
    'BackupCreator',
    'BackupRestorer',
    'BackupManagerDialog',
    'ResumeManager',
]

