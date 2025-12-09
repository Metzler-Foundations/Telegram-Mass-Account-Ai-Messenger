#!/usr/bin/env python3
"""A/B test statistical significance calculator."""

import logging
import math
from dataclasses import dataclass
from typing import Dict, Tuple

logger = logging.getLogger(__name__)


@dataclass
class ABTestResult:
    """A/B test statistical result."""

    variant_a_rate: float
    variant_b_rate: float
    absolute_difference: float
    relative_improvement: float
    z_score: float
    p_value: float
    is_significant: bool
    confidence_level: float
    sample_size_a: int
    sample_size_b: int
    recommendation: str


class ABTestCalculator:
    """Calculate statistical significance for A/B tests."""

    # Z-score thresholds for different confidence levels
    Z_SCORES = {
        0.90: 1.645,  # 90% confidence
        0.95: 1.960,  # 95% confidence (standard)
        0.99: 2.576,  # 99% confidence
    }

    @staticmethod
    def calculate_significance(
        variant_a_conversions: int,
        variant_a_total: int,
        variant_b_conversions: int,
        variant_b_total: int,
        confidence_level: float = 0.95,
    ) -> ABTestResult:
        """
        Calculate statistical significance between two variants.

        Args:
            variant_a_conversions: Number of conversions for variant A
            variant_a_total: Total impressions for variant A
            variant_b_conversions: Number of conversions for variant B
            variant_b_total: Total impressions for variant B
            confidence_level: Desired confidence level (0.90, 0.95, or 0.99)

        Returns:
            ABTestResult with statistical analysis
        """
        # Validate inputs
        if variant_a_total <= 0 or variant_b_total <= 0:
            logger.error("Sample sizes must be positive")
            return ABTestCalculator._create_invalid_result()

        if variant_a_conversions < 0 or variant_b_conversions < 0:
            logger.error("Conversions cannot be negative")
            return ABTestCalculator._create_invalid_result()

        if variant_a_conversions > variant_a_total or variant_b_conversions > variant_b_total:
            logger.error("Conversions cannot exceed total")
            return ABTestCalculator._create_invalid_result()

        # Calculate conversion rates
        rate_a = variant_a_conversions / variant_a_total
        rate_b = variant_b_conversions / variant_b_total

        # Calculate pooled standard error
        pooled_rate = (variant_a_conversions + variant_b_conversions) / (
            variant_a_total + variant_b_total
        )
        se = math.sqrt(
            pooled_rate * (1 - pooled_rate) * (1 / variant_a_total + 1 / variant_b_total)
        )

        # Handle zero standard error (both rates are 0 or 1)
        if se == 0:
            z_score = 0.0
            p_value = 1.0
        else:
            # Calculate Z-score
            z_score = (rate_b - rate_a) / se

            # Calculate two-tailed p-value
            p_value = 2 * (1 - ABTestCalculator._standard_normal_cdf(abs(z_score)))

        # Determine significance
        z_threshold = ABTestCalculator.Z_SCORES.get(confidence_level, 1.960)
        is_significant = abs(z_score) >= z_threshold

        # Calculate differences
        absolute_diff = rate_b - rate_a
        relative_improvement = ((rate_b - rate_a) / rate_a * 100) if rate_a > 0 else 0.0

        # Generate recommendation
        recommendation = ABTestCalculator._generate_recommendation(
            is_significant, rate_a, rate_b, variant_a_total, variant_b_total
        )

        return ABTestResult(
            variant_a_rate=rate_a * 100,  # Convert to percentage
            variant_b_rate=rate_b * 100,
            absolute_difference=absolute_diff * 100,
            relative_improvement=relative_improvement,
            z_score=z_score,
            p_value=p_value,
            is_significant=is_significant,
            confidence_level=confidence_level * 100,
            sample_size_a=variant_a_total,
            sample_size_b=variant_b_total,
            recommendation=recommendation,
        )

    @staticmethod
    def _standard_normal_cdf(z: float) -> float:
        """Calculate cumulative distribution function for standard normal distribution."""
        # Using error function approximation
        return 0.5 * (1 + math.erf(z / math.sqrt(2)))

    @staticmethod
    def _generate_recommendation(
        is_significant: bool, rate_a: float, rate_b: float, n_a: int, n_b: int
    ) -> str:
        """Generate recommendation based on test results."""
        # Check sample size adequacy
        min_sample_size = 100
        if n_a < min_sample_size or n_b < min_sample_size:
            return f"⚠️ Insufficient sample size (min {min_sample_size}). Continue collecting data."

        if not is_significant:
            improvement = ((rate_b - rate_a) / rate_a * 100) if rate_a > 0 else 0
            if abs(improvement) < 5:
                return "No significant difference. Both variants perform similarly."
            else:
                return (
                    f"Trend suggests {abs(improvement):.1f}% difference but "
                    f"not statistically significant yet. Continue testing."
                )

        # Significant result
        if rate_b > rate_a:
            improvement = (rate_b - rate_a) / rate_a * 100
            return f"✅ Variant B wins! {improvement:.1f}% improvement (statistically significant)"
        elif rate_a > rate_b:
            decline = (rate_a - rate_b) / rate_a * 100
            return (
                f"✅ Variant A wins! Variant B performs {decline:.1f}% worse "
                f"(statistically significant)"
            )
        else:
            return "Both variants perform identically."

    @staticmethod
    def _create_invalid_result() -> ABTestResult:
        """Create result object for invalid inputs."""
        return ABTestResult(
            variant_a_rate=0.0,
            variant_b_rate=0.0,
            absolute_difference=0.0,
            relative_improvement=0.0,
            z_score=0.0,
            p_value=1.0,
            is_significant=False,
            confidence_level=95.0,
            sample_size_a=0,
            sample_size_b=0,
            recommendation="❌ Invalid test data. Check inputs.",
        )

    @staticmethod
    def calculate_required_sample_size(
        baseline_rate: float,
        minimum_detectable_effect: float,
        confidence_level: float = 0.95,
        statistical_power: float = 0.80,
    ) -> int:
        """
        Calculate required sample size per variant.

        Args:
            baseline_rate: Expected baseline conversion rate (0-1)
            minimum_detectable_effect: Minimum effect to detect (e.g., 0.05 for 5%)
            confidence_level: Desired confidence level
            statistical_power: Desired statistical power

        Returns:
            Required sample size per variant
        """
        if baseline_rate <= 0 or baseline_rate >= 1:
            logger.error(f"Invalid baseline rate: {baseline_rate}")
            return 1000  # Default

        # Z-scores for alpha and beta
        z_alpha = ABTestCalculator.Z_SCORES.get(confidence_level, 1.960)
        z_beta = 0.842  # For 80% power

        # Effect size
        effect_size = minimum_detectable_effect

        # Pooled variance
        p1 = baseline_rate
        p2 = baseline_rate * (1 + effect_size)
        pooled_p = (p1 + p2) / 2

        # Calculate sample size
        numerator = 2 * pooled_p * (1 - pooled_p) * (z_alpha + z_beta) ** 2
        denominator = (p2 - p1) ** 2

        if denominator == 0:
            return 10000  # Very large sample if no effect

        n = math.ceil(numerator / denominator)

        logger.info(f"Required sample size: {n} per variant for {effect_size*100}% MDE")
        return max(n, 100)  # Minimum 100

    @staticmethod
    def is_test_complete(
        n_a: int, n_b: int, required_n: int, is_significant: bool, min_runtime_days: int = 7
    ) -> Tuple[bool, str]:
        """
        Determine if A/B test is complete.

        Returns:
            (is_complete, reason)
        """
        # Check minimum sample size
        if n_a < required_n or n_b < required_n:
            remaining_a = max(0, required_n - n_a)
            remaining_b = max(0, required_n - n_b)
            return False, f"Need {remaining_a} more samples for A, {remaining_b} for B"

        # If significant and minimum samples reached, complete
        if is_significant and n_a >= required_n and n_b >= required_n:
            return True, "Statistically significant result with sufficient samples"

        # If both variants have 2x required samples but still not significant
        if n_a >= required_n * 2 and n_b >= required_n * 2:
            return True, "Maximum samples reached - no significant difference detected"

        return False, "Continue collecting data"


def calculate_ab_test(
    variant_a_conversions: int,
    variant_a_total: int,
    variant_b_conversions: int,
    variant_b_total: int,
) -> Dict:
    """Convenience function to calculate A/B test (returns dict)."""
    result = ABTestCalculator.calculate_significance(
        variant_a_conversions, variant_a_total, variant_b_conversions, variant_b_total
    )

    return {
        "variant_a_rate": result.variant_a_rate,
        "variant_b_rate": result.variant_b_rate,
        "absolute_difference": result.absolute_difference,
        "relative_improvement": result.relative_improvement,
        "z_score": result.z_score,
        "p_value": result.p_value,
        "is_significant": result.is_significant,
        "confidence_level": result.confidence_level,
        "recommendation": result.recommendation,
    }
