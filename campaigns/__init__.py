"""
Campaign management module.
"""
# Lazy imports to avoid circular dependencies
def __getattr__(name):
    if name in ('DMCampaignManager', 'MessageTemplateEngine', 'CampaignStatus'):
        from . import dm_campaign_manager
        return getattr(dm_campaign_manager, name)
    elif name in ('CampaignProgressTracker', 'initialize_campaign_database', 
                  'save_campaign_message', 'update_campaign_status'):
        from . import campaign_tracker
        return getattr(campaign_tracker, name)
    elif name in ('EngagementAutomation', 'EngagementStrategy', 'EngagementRule'):
        from . import engagement_automation
        return getattr(engagement_automation, name)
    elif name == 'TemplateTester':
        from .template_tester import TemplateTester
        return TemplateTester
    elif name == 'IntelligentScheduler':
        from .intelligent_scheduler import IntelligentScheduler
        return IntelligentScheduler
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    'DMCampaignManager',
    'MessageTemplateEngine',
    'CampaignStatus',
    'CampaignProgressTracker',
    'initialize_campaign_database',
    'save_campaign_message',
    'update_campaign_status',
    'EngagementAutomation',
    'EngagementStrategy',
    'EngagementRule',
    'TemplateTester',
    'IntelligentScheduler',
]

