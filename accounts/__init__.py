"""
Account management module.
"""


# Lazy imports to avoid circular dependencies
def __getattr__(name):
    if name == "AccountManager":
        from .account_manager import AccountManager

        return AccountManager
    elif name == "AccountCreator":
        from .account_creator import AccountCreator

        return AccountCreator
    elif name == "AccountWarmupService":
        from .account_warmup_service import AccountWarmupService

        return AccountWarmupService
    elif name in ("AccountCreationFailSafe", "FailSafeLevel"):
        from . import account_creation_failsafes

        return getattr(account_creation_failsafes, name)
    elif name == "WarmupTracker":
        from .warmup_tracker import WarmupTracker

        return WarmupTracker
    elif name == "UsernameGenerator":
        from .username_generator import UsernameGenerator

        return UsernameGenerator
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "AccountManager",
    "AccountCreator",
    "AccountWarmupService",
    "AccountCreationFailSafe",
    "FailSafeLevel",
    "WarmupTracker",
    "UsernameGenerator",
]
