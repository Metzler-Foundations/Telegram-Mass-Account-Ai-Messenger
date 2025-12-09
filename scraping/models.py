#!/usr/bin/env python3
"""
Scraping Data Models - Core data structures for member scraping.

Contains dataclasses and enums for scraping-related data.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Tuple


@dataclass
class ScrapingRisk:
    """Risk assessment for scraping operations."""

    level: str  # 'low', 'medium', 'high', 'critical'
    score: float
    factors: List[str]
    recommendations: List[str]
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


@dataclass
class AccountHealth:
    """Health metrics for scraping accounts."""

    account_id: str
    flood_wait_count: int = 0
    last_flood_wait: Optional[datetime] = None
    error_count: int = 0
    last_error: Optional[str] = None
    success_rate: float = 1.0
    total_requests: int = 0
    successful_requests: int = 0
    avg_response_time: float = 0.0
    is_active: bool = True
    ban_risk_level: str = "low"
    last_health_check: Optional[datetime] = None


@dataclass
class SessionMetrics:
    """Metrics for scraping sessions."""

    session_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    total_members_scraped: int = 0
    total_groups_processed: int = 0
    errors_encountered: int = 0
    flood_waits: int = 0
    avg_members_per_group: float = 0.0
    success_rate: float = 0.0
    duration_seconds: Optional[float] = None

    def complete_session(self):
        """Mark session as complete and calculate final metrics."""
        self.end_time = datetime.now()
        if self.start_time:
            self.duration_seconds = (self.end_time - self.start_time).total_seconds()


@dataclass
class GeographicProfile:
    """Geographic distribution of scraped members."""

    country_distribution: Dict[str, int]
    city_distribution: Dict[str, int]
    timezone_distribution: Dict[str, int]
    total_profiles: int = 0
    completeness_score: float = 0.0

    def add_location(self, country: Optional[str], city: Optional[str], timezone: Optional[str]):
        """Add a location to the profile."""
        if country:
            self.country_distribution[country] = self.country_distribution.get(country, 0) + 1
        if city:
            self.city_distribution[city] = self.city_distribution.get(city, 0) + 1
        if timezone:
            self.timezone_distribution[timezone] = self.timezone_distribution.get(timezone, 0) + 1
        self.total_profiles += 1

    def get_top_countries(self, limit: int = 5) -> List[Tuple[str, int]]:
        """Get top countries by member count."""
        return sorted(self.country_distribution.items(), key=lambda x: x[1], reverse=True)[:limit]


class ScrapingMethod(Enum):
    """Methods for member scraping."""

    MEMBERS = "members"
    PARTICIPANTS = "participants"
    ADMIN_LIST = "admin_list"
    RECENT_ACTIVITY = "recent_activity"
    BULK_PARTICIPANT_FETCH = "bulk_participant_fetch"


class JobStatus(Enum):
    """Status of scraping jobs."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ScrapingJob:
    """Represents a scraping job."""

    job_id: str
    group_id: int
    method: ScrapingMethod
    status: JobStatus = JobStatus.PENDING
    created_at: datetime = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    members_found: int = 0
    errors: List[str] = None
    retry_count: int = 0
    max_retries: int = 3

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.errors is None:
            self.errors = []


@dataclass
class ScrapingConfig:
    """Configuration for scraping operations."""

    batch_size: int = 100
    delay_between_batches: float = 1.0
    max_concurrent_groups: int = 5
    respect_flood_wait: bool = True
    enable_anti_detection: bool = True
    max_members_per_group: int = 10000
    timeout_per_group: int = 300  # 5 minutes
    retry_failed_groups: bool = True
    max_retries_per_group: int = 3


def calculate_risk_score(
    flood_waits: int, errors: int, total_requests: int, time_window_hours: int = 24
) -> ScrapingRisk:
    """
    Calculate scraping risk score based on recent activity.

    Args:
        flood_waits: Number of flood waits in time window
        errors: Number of errors in time window
        total_requests: Total requests in time window
        time_window_hours: Hours to consider for risk calculation

    Returns:
        ScrapingRisk assessment
    """
    if total_requests == 0:
        return ScrapingRisk(
            level="low", score=0.0, factors=[], recommendations=["No recent activity to assess"]
        )

    # Calculate risk factors
    flood_rate = flood_waits / total_requests
    error_rate = errors / total_requests

    # Base risk score
    risk_score = (flood_rate * 50) + (error_rate * 30)

    # Additional factors
    factors = []
    recommendations = []

    if flood_rate > 0.1:  # >10% flood waits
        factors.append(f"High flood wait rate: {flood_rate:.1%}")
        recommendations.append("Reduce scraping frequency")
        risk_score += 20

    if error_rate > 0.2:  # >20% errors
        factors.append(f"High error rate: {error_rate:.1%}")
        recommendations.append("Check account health and permissions")
        risk_score += 15

    if total_requests > 1000:  # High volume
        factors.append(f"High request volume: {total_requests}")
        recommendations.append("Consider distributing load across multiple accounts")
        risk_score += 10

    # Determine risk level
    if risk_score >= 70:
        level = "critical"
    elif risk_score >= 50:
        level = "high"
    elif risk_score >= 30:
        level = "medium"
    else:
        level = "low"

    return ScrapingRisk(
        level=level, score=min(risk_score, 100.0), factors=factors, recommendations=recommendations
    )
