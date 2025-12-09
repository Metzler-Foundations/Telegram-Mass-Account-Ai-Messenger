"""
Database layer module.
"""


# Lazy imports to avoid circular dependencies
def __getattr__(name):
    if name == "DatabasePool":
        from .database_pool import DatabasePool

        return DatabasePool
    elif name in (
        "DatabaseQueryHelper",
        "MemberQueries",
        "CampaignQueries",
        "AccountQueries",
        "member_queries",
        "campaign_queries",
        "account_queries",
    ):
        from . import database_queries

        return getattr(database_queries, name)
    elif name == "QueryCache":
        from .query_cache import QueryCache

        return QueryCache
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "DatabasePool",
    "DatabaseQueryHelper",
    "MemberQueries",
    "CampaignQueries",
    "AccountQueries",
    "member_queries",
    "campaign_queries",
    "account_queries",
    "QueryCache",
]
