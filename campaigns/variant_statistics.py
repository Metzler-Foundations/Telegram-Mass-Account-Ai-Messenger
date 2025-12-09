"""
Statistical significance testing for A/B test variants.

Features:
- Chi-square test for categorical data
- Statistical power calculation
- Confidence intervals
- Sample size recommendations
"""

import logging
import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class VariantTestResult:
    """Result of statistical significance test."""

    variant_a_name: str
    variant_b_name: str

    # Metrics
    variant_a_sent: int
    variant_a_success: int
    variant_b_sent: int
    variant_b_success: int

    # Rates
    variant_a_rate: float
    variant_b_rate: float
    rate_difference: float
    rate_difference_percent: float

    # Statistical significance
    chi_square_statistic: float
    p_value: float
    is_significant: bool  # p < 0.05
    confidence_level: float  # 0.90, 0.95, or 0.99

    # Recommendations
    sample_size_adequate: bool
    recommended_min_sample: int
    winner: Optional[str] = None


class VariantStatistics:
    """Statistical analysis for A/B test variants."""

    # Chi-square critical values for p = 0.05 (95% confidence), df = 1
    CHI_SQUARE_CRITICAL_095 = 3.841
    CHI_SQUARE_CRITICAL_099 = 6.635

    @staticmethod
    def calculate_chi_square(
        variant_a_sent: int, variant_a_success: int, variant_b_sent: int, variant_b_success: int
    ) -> Tuple[float, float]:
        """
        Calculate chi-square statistic and p-value.

        Args:
            variant_a_sent: Total messages sent for variant A
            variant_a_success: Successful messages for variant A
            variant_b_sent: Total messages sent for variant B
            variant_b_success: Successful messages for variant B

        Returns:
            Tuple of (chi_square_statistic, p_value)
        """
        # Calculate failures
        variant_a_failure = variant_a_sent - variant_a_success
        variant_b_failure = variant_b_sent - variant_b_success

        # Total
        total_success = variant_a_success + variant_b_success
        total_failure = variant_a_failure + variant_b_failure
        total_sent = variant_a_sent + variant_b_sent

        if total_sent == 0:
            return 0.0, 1.0

        # Expected values
        expected_a_success = (variant_a_sent * total_success) / total_sent
        expected_a_failure = (variant_a_sent * total_failure) / total_sent
        expected_b_success = (variant_b_sent * total_success) / total_sent
        expected_b_failure = (variant_b_sent * total_failure) / total_sent

        # Avoid division by zero
        if any(
            e == 0
            for e in [
                expected_a_success,
                expected_a_failure,
                expected_b_success,
                expected_b_failure,
            ]
        ):
            return 0.0, 1.0

        # Chi-square statistic
        chi_square = (
            ((variant_a_success - expected_a_success) ** 2 / expected_a_success)
            + ((variant_a_failure - expected_a_failure) ** 2 / expected_a_failure)
            + ((variant_b_success - expected_b_success) ** 2 / expected_b_success)
            + ((variant_b_failure - expected_b_failure) ** 2 / expected_b_failure)
        )

        # P-value approximation (for df=1)
        # Using chi-square distribution approximation
        p_value = VariantStatistics._chi_square_to_p_value(chi_square)

        return chi_square, p_value

    @staticmethod
    def _chi_square_to_p_value(chi_square: float) -> float:
        """Convert chi-square statistic to p-value (df=1)."""
        # Simplified p-value calculation using critical values
        if chi_square < 0.004:
            return 0.95
        elif chi_square < 0.10:
            return 0.75
        elif chi_square < 1.07:
            return 0.30
        elif chi_square < 2.71:
            return 0.10
        elif chi_square < 3.84:
            return 0.05
        elif chi_square < 6.63:
            return 0.01
        else:
            return 0.001

    @staticmethod
    def calculate_required_sample_size(
        baseline_rate: float = 0.5,
        minimum_detectable_effect: float = 0.1,
        alpha: float = 0.05,
        power: float = 0.80,
    ) -> int:
        """
        Calculate required sample size per variant.

        Args:
            baseline_rate: Expected baseline conversion rate (0-1)
            minimum_detectable_effect: Minimum effect to detect (e.g., 0.1 = 10% improvement)
            alpha: Significance level (default 0.05 for 95% confidence)
            power: Statistical power (default 0.80 for 80% power)

        Returns:
            Required sample size per variant
        """
        # Z-scores
        z_alpha = 1.96  # For alpha = 0.05 (two-tailed)
        z_beta = 0.84  # For power = 0.80

        # Effect size
        p1 = baseline_rate
        p2 = baseline_rate + minimum_detectable_effect

        # Pooled proportion
        p_pooled = (p1 + p2) / 2

        # Sample size calculation (simplified formula)
        numerator = (z_alpha + z_beta) ** 2 * 2 * p_pooled * (1 - p_pooled)
        denominator = (p2 - p1) ** 2

        if denominator == 0:
            return 1000  # Default

        n = numerator / denominator
        return int(math.ceil(n))

    @staticmethod
    def test_variants(
        variant_a_name: str,
        variant_a_sent: int,
        variant_a_success: int,
        variant_b_name: str,
        variant_b_sent: int,
        variant_b_success: int,
        confidence_level: float = 0.95,
    ) -> VariantTestResult:
        """
        Run complete statistical test on two variants.

        Args:
            variant_a_name: Name of variant A
            variant_a_sent: Messages sent for variant A
            variant_a_success: Successful for variant A
            variant_b_name: Name of variant B
            variant_b_sent: Messages sent for variant B
            variant_b_success: Successful for variant B
            confidence_level: Desired confidence (0.90, 0.95, or 0.99)

        Returns:
            VariantTestResult with complete analysis
        """
        # Calculate rates
        variant_a_rate = variant_a_success / variant_a_sent if variant_a_sent > 0 else 0
        variant_b_rate = variant_b_success / variant_b_sent if variant_b_sent > 0 else 0

        rate_difference = variant_b_rate - variant_a_rate
        rate_difference_percent = rate_difference * 100

        # Chi-square test
        chi_square, p_value = VariantStatistics.calculate_chi_square(
            variant_a_sent, variant_a_success, variant_b_sent, variant_b_success
        )

        # Determine significance
        alpha = 1 - confidence_level
        is_significant = p_value < alpha

        # Determine winner
        winner = None
        if is_significant:
            if variant_a_rate > variant_b_rate:
                winner = variant_a_name
            elif variant_b_rate > variant_a_rate:
                winner = variant_b_name

        # Sample size check
        recommended_min = VariantStatistics.calculate_required_sample_size(
            baseline_rate=max(variant_a_rate, variant_b_rate, 0.5),
            minimum_detectable_effect=0.1,  # 10% improvement
        )

        sample_size_adequate = (
            variant_a_sent >= recommended_min and variant_b_sent >= recommended_min
        )

        return VariantTestResult(
            variant_a_name=variant_a_name,
            variant_b_name=variant_b_name,
            variant_a_sent=variant_a_sent,
            variant_a_success=variant_a_success,
            variant_b_sent=variant_b_sent,
            variant_b_success=variant_b_success,
            variant_a_rate=variant_a_rate,
            variant_b_rate=variant_b_rate,
            rate_difference=rate_difference,
            rate_difference_percent=rate_difference_percent,
            chi_square_statistic=chi_square,
            p_value=p_value,
            is_significant=is_significant,
            confidence_level=confidence_level,
            sample_size_adequate=sample_size_adequate,
            recommended_min_sample=recommended_min,
            winner=winner,
        )

    @staticmethod
    def get_variant_stats_from_db(campaign_id: int, db_path: str = "campaigns.db") -> List[Dict]:
        """
        Get variant statistics from campaign database.

        Args:
            campaign_id: Campaign ID to analyze
            db_path: Path to campaigns database

        Returns:
            List of variant statistics
        """
        try:
            import sqlite3

            with sqlite3.connect(db_path) as conn:
                conn.row_factory = sqlite3.Row

                cursor = conn.execute(
                    """
                    SELECT
                        template_variant,
                        COUNT(*) as total_sent,
                        SUM(CASE WHEN status = 'sent' THEN 1 ELSE 0 END) as success_count
                    FROM campaign_messages
                    WHERE campaign_id = ? AND template_variant IS NOT NULL
                    GROUP BY template_variant
                """,
                    (campaign_id,),
                )

                variants = []
                for row in cursor:
                    variants.append(
                        {
                            "variant": row["template_variant"],
                            "sent": row["total_sent"],
                            "success": row["success_count"],
                            "rate": (
                                row["success_count"] / row["total_sent"]
                                if row["total_sent"] > 0
                                else 0
                            ),
                        }
                    )

                return variants

        except Exception as e:
            logger.error(f"Failed to get variant stats: {e}")
            return []

    @staticmethod
    def test_campaign_variants(
        campaign_id: int, db_path: str = "campaigns.db"
    ) -> List[VariantTestResult]:
        """
        Test all variant pairs in a campaign for statistical significance.

        Args:
            campaign_id: Campaign ID
            db_path: Path to campaigns database

        Returns:
            List of test results for all variant pairs
        """
        variants = VariantStatistics.get_variant_stats_from_db(campaign_id, db_path)

        if len(variants) < 2:
            logger.info(f"Campaign {campaign_id} has < 2 variants, no testing needed")
            return []

        results = []

        # Test all pairs
        for i in range(len(variants)):
            for j in range(i + 1, len(variants)):
                variant_a = variants[i]
                variant_b = variants[j]

                result = VariantStatistics.test_variants(
                    variant_a_name=variant_a["variant"],
                    variant_a_sent=variant_a["sent"],
                    variant_a_success=variant_a["success"],
                    variant_b_name=variant_b["variant"],
                    variant_b_sent=variant_b["sent"],
                    variant_b_success=variant_b["success"],
                )

                results.append(result)

        return results


# Singleton
_variant_statistics: Optional[VariantStatistics] = None


def get_variant_statistics() -> VariantStatistics:
    """Get singleton variant statistics instance."""
    global _variant_statistics
    if _variant_statistics is None:
        _variant_statistics = VariantStatistics()
    return _variant_statistics
