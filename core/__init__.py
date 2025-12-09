"""
Core business logic and services module.
"""


# Lazy imports to avoid circular dependencies
def __getattr__(name):
    if name in (
        "BaseService",
        "MemberService",
        "CampaignService",
        "AccountService",
        "BusinessLogicCoordinator",
    ):
        from . import services

        return getattr(services, name)
    elif name in ("BaseRepository", "MemberRepository", "CampaignRepository", "AccountRepository"):
        from . import repositories

        return getattr(repositories, name)
    elif name == "ServiceContainer":
        from .service_container import ServiceContainer

        return ServiceContainer
    elif name == "ErrorHandler":
        from .error_handler import ErrorHandler

        return ErrorHandler
    elif name == "ConfigManager":
        from .config_manager import ConfigManager

        return ConfigManager
    elif name == "ConfigSecurity":
        from .config_security import ConfigSecurity

        return ConfigSecurity
    elif name == "setup_logging":
        from .setup_logging import setup_logging

        return setup_logging
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "BaseService",
    "MemberService",
    "CampaignService",
    "AccountService",
    "BusinessLogicCoordinator",
    "BaseRepository",
    "MemberRepository",
    "CampaignRepository",
    "AccountRepository",
    "ServiceContainer",
    "ErrorHandler",
    "ConfigManager",
    "ConfigSecurity",
    "setup_logging",
]
