"""
User interface module.
"""


# Lazy imports to avoid circular dependencies
def __getattr__(name):
    if name == "UIController":
        from .ui_controller import UIController

        return UIController
    elif name in ("CampaignManagerWidget", "MessageHistoryWidget", "LoadingOverlay"):
        from . import ui_components

        return getattr(ui_components, name)
    elif name == "SettingsWindow":
        from .settings_window import SettingsWindow

        return SettingsWindow
    elif name == "WelcomeWizard":
        from .welcome_wizard import WelcomeWizard

        return WelcomeWizard
    elif name == "AnalyticsDashboard":
        from .analytics_dashboard import AnalyticsDashboard

        return AnalyticsDashboard
    elif name == "AccountHealthWidget":
        from .account_health_widget import AccountHealthWidget

        return AccountHealthWidget
    elif name == "CampaignAnalyticsWidget":
        from .campaign_analytics_widget import CampaignAnalyticsWidget

        return CampaignAnalyticsWidget
    elif name == "ProxyManagementWidget":
        from .proxy_management_widget import ProxyManagementWidget

        return ProxyManagementWidget
    elif name == "DISCORD_THEME":
        from .ui_redesign import DISCORD_THEME

        return DISCORD_THEME
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "UIController",
    "CampaignManagerWidget",
    "MessageHistoryWidget",
    "LoadingOverlay",
    "SettingsWindow",
    "WelcomeWizard",
    "AnalyticsDashboard",
    "AccountHealthWidget",
    "CampaignAnalyticsWidget",
    "ProxyManagementWidget",
    "DISCORD_THEME",
]
