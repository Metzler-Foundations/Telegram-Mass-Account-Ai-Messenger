"""
Member scraping and discovery module.
"""


# Lazy imports to avoid circular dependencies
def __getattr__(name):
    if name in (
        "MemberScraper",
        "MemberDatabase",
        "EliteAntiDetectionSystem",
        "ComprehensiveDataExtractor",
        "EliteMemberScraper",
    ):
        from . import member_scraper

        return getattr(member_scraper, name)
    elif name in ("MemberFilterDialog", "FilterPresetManager", "show_filter_dialog"):
        from . import member_filter

        return getattr(member_filter, name)
    elif name == "GroupDiscoveryEngine":
        from .group_discovery_engine import GroupDiscoveryEngine

        return GroupDiscoveryEngine
    elif name == "RelationshipMapper":
        from .relationship_mapper import RelationshipMapper

        return RelationshipMapper
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "MemberScraper",
    "MemberDatabase",
    "EliteAntiDetectionSystem",
    "ComprehensiveDataExtractor",
    "EliteMemberScraper",
    "MemberFilterDialog",
    "FilterPresetManager",
    "show_filter_dialog",
    "GroupDiscoveryEngine",
    "RelationshipMapper",
]
