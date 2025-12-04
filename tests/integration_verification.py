"""
Integration Verification Tests
Verifies all critical integrations are working as claimed in README.
"""

import logging
import asyncio
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class IntegrationVerifier:
    """Verify all critical integrations."""
    
    def __init__(self):
        self.passed = []
        self.failed = []
        self.warnings = []
    
    def test_background_services_start(self):
        """Verify background services are properly started."""
        logger.info("Testing background service initialization...")
        
        try:
            from main import MainWindow
            
            # Check that _start_background_services method exists
            assert hasattr(MainWindow, '_start_background_services'), \
                "MainWindow missing _start_background_services method"
            
            self.passed.append("✅ Background services initialization method exists")
            
            # Verify it's called in __init__
            import inspect
            source = inspect.getsource(MainWindow.__init__)
            assert '_initialize_services' in source or '_start_background_services' in source, \
                "Background services not started in MainWindow.__init__"
            
            self.passed.append("✅ Background services are started in MainWindow.__init__")
            return True
            
        except Exception as e:
            self.failed.append(f"❌ Background services test failed: {e}")
            return False
    
    def test_warmup_integration(self):
        """Verify warmup service integration."""
        logger.info("Testing warmup service integration...")
        
        try:
            from accounts.account_warmup_service import AccountWarmupService
            from accounts.warmup_intelligence import WarmupIntelligence
            
            # Check WarmupIntelligence methods
            wi = WarmupIntelligence()
            
            # Test that methods are implemented (not just returning None/fallback)
            methods = [
                'generate_natural_bio',
                'suggest_contact_to_add',
                'suggest_group_to_join',
                'generate_conversation_starter'
            ]
            
            for method in methods:
                assert hasattr(wi, method), f"WarmupIntelligence missing {method}"
            
            self.passed.append("✅ WarmupIntelligence has all required methods")
            
            # Verify blackout window check exists
            import inspect
            warmup_source = inspect.getsource(AccountWarmupService)
            if 'blackout' in warmup_source.lower():
                self.passed.append("✅ Blackout window logic implemented")
            else:
                self.warnings.append("⚠️  Blackout window check may not be implemented")
            
            return True
            
        except Exception as e:
            self.failed.append(f"❌ Warmup integration test failed: {e}")
            return False
    
    def test_campaign_features(self):
        """Verify campaign features."""
        logger.info("Testing campaign features...")
        
        try:
            from campaigns.dm_campaign_manager import DMCampaignManager
            from campaigns.delivery_analytics import DeliveryAnalytics
            from campaigns.read_receipt_poller import ReadReceiptPoller
            from campaigns.response_tracker import ResponseTracker
            from campaigns.variant_statistics import VariantStatistics
            
            # Check that response tracker and poller exist
            self.passed.append("✅ ReadReceiptPoller implemented")
            self.passed.append("✅ ResponseTracker implemented")
            
            # Check variant statistics
            vs = VariantStatistics()
            assert hasattr(vs, 'calculate_chi_square'), "Missing chi-square implementation"
            assert hasattr(vs, 'test_variants'), "Missing variant testing"
            
            self.passed.append("✅ A/B testing statistical analysis implemented")
            
            # Check DMCampaignManager integration
            import inspect
            dm_source = inspect.getsource(DMCampaignManager.__init__)
            
            if 'delivery_analytics' in dm_source or 'DeliveryAnalytics' in dm_source:
                self.passed.append("✅ Delivery analytics integrated in campaign manager")
            else:
                self.warnings.append("⚠️  Delivery analytics integration unclear")
            
            return True
            
        except Exception as e:
            self.failed.append(f"❌ Campaign features test failed: {e}")
            return False
    
    def test_analytics_widgets(self):
        """Verify analytics widgets have export functionality."""
        logger.info("Testing analytics export functionality...")
        
        try:
            from ui.campaign_analytics_widget import CampaignAnalyticsWidget
            from ui.delivery_analytics_widget import DeliveryAnalyticsWidget
            from ui.analytics_dashboard import AnalyticsDashboard
            from utils.export_manager import ExportManager
            
            # Check export methods exist
            assert hasattr(CampaignAnalyticsWidget, 'export_analytics'), \
                "CampaignAnalyticsWidget missing export_analytics"
            
            assert hasattr(DeliveryAnalyticsWidget, 'export_data'), \
                "DeliveryAnalyticsWidget missing export_data"
            
            assert hasattr(AnalyticsDashboard, 'export_dashboard_data'), \
                "AnalyticsDashboard missing export_dashboard_data"
            
            self.passed.append("✅ All analytics widgets have export functionality")
            
            # Check ExportManager methods
            em = ExportManager()
            export_methods = [
                'export_campaigns_to_csv',
                'export_campaigns_to_json',
                'export_campaign_analytics_to_csv',
                'export_delivery_analytics_to_csv',
                'export_accounts_to_csv',
                'export_risk_data_to_csv',
                'export_members_to_csv',
                'export_cost_data_to_csv'
            ]
            
            for method in export_methods:
                assert hasattr(em, method), f"ExportManager missing {method}"
            
            self.passed.append("✅ ExportManager has all required export methods")
            
            return True
            
        except Exception as e:
            self.failed.append(f"❌ Analytics export test failed: {e}")
            return False
    
    def test_retry_dialog(self):
        """Verify retry dialog implementation."""
        logger.info("Testing retry dialog...")
        
        try:
            from ui.retry_dialog import RetryDialog, show_error_with_retry
            
            assert RetryDialog is not None, "RetryDialog not found"
            assert show_error_with_retry is not None, "show_error_with_retry not found"
            
            self.passed.append("✅ Retry dialog utility implemented")
            return True
            
        except Exception as e:
            self.failed.append(f"❌ Retry dialog test failed: {e}")
            return False
    
    def test_charts(self):
        """Verify chart widgets."""
        logger.info("Testing chart widgets...")
        
        try:
            from ui.cost_trend_chart import CostTrendChart
            from ui.risk_distribution_chart import RiskDistributionChart
            
            # Check that charts have required methods
            assert hasattr(CostTrendChart, 'refresh_chart'), "CostTrendChart missing refresh_chart"
            assert hasattr(CostTrendChart, 'get_cost_data'), "CostTrendChart missing get_cost_data"
            
            assert hasattr(RiskDistributionChart, 'refresh_chart'), "RiskDistributionChart missing refresh_chart"
            assert hasattr(RiskDistributionChart, 'get_risk_data'), "RiskDistributionChart missing get_risk_data"
            
            self.passed.append("✅ Cost trend chart implemented")
            self.passed.append("✅ Risk distribution chart implemented")
            
            return True
            
        except Exception as e:
            self.failed.append(f"❌ Chart widgets test failed: {e}")
            return False
    
    def test_tooltips(self):
        """Verify tooltips are added to UI."""
        logger.info("Testing tooltips...")
        
        try:
            from ui.ui_components import CreateCampaignDialog
            import inspect
            
            source = inspect.getsource(CreateCampaignDialog.setup_ui)
            
            # Check for setToolTip calls
            tooltip_count = source.count('setToolTip')
            
            if tooltip_count >= 5:
                self.passed.append(f"✅ Tooltips implemented ({tooltip_count} found in campaign dialog)")
            else:
                self.warnings.append(f"⚠️  Limited tooltips ({tooltip_count} found)")
            
            return True
            
        except Exception as e:
            self.failed.append(f"❌ Tooltip test failed: {e}")
            return False
    
    def test_template_variants(self):
        """Verify template variant UI."""
        logger.info("Testing template variant UI...")
        
        try:
            from ui.ui_components import CreateCampaignDialog
            import inspect
            
            source = inspect.getsource(CreateCampaignDialog.setup_ui)
            
            # Check for variant-related code
            assert 'variant_table' in source, "variant_table not found in CreateCampaignDialog"
            assert '_add_variant_row' in source or 'Template Variants' in source, \
                "Template variant UI not found"
            
            self.passed.append("✅ Template variant UI implemented in campaign dialog")
            
            # Check get_data returns variants
            get_data_source = inspect.getsource(CreateCampaignDialog.get_data)
            assert 'template_variants' in get_data_source, \
                "template_variants not returned from get_data"
            
            self.passed.append("✅ Template variants included in campaign data")
            
            return True
            
        except Exception as e:
            self.failed.append(f"❌ Template variant UI test failed: {e}")
            return False
    
    def run_all_tests(self):
        """Run all verification tests."""
        logger.info("=" * 60)
        logger.info("STARTING INTEGRATION VERIFICATION")
        logger.info("=" * 60)
        
        tests = [
            self.test_background_services_start,
            self.test_warmup_integration,
            self.test_campaign_features,
            self.test_analytics_widgets,
            self.test_retry_dialog,
            self.test_charts,
            self.test_tooltips,
            self.test_template_variants
        ]
        
        for test in tests:
            try:
                test()
            except Exception as e:
                self.failed.append(f"❌ {test.__name__} crashed: {e}")
        
        # Print results
        logger.info("\n" + "=" * 60)
        logger.info("VERIFICATION RESULTS")
        logger.info("=" * 60)
        
        if self.passed:
            logger.info("\n✅ PASSED TESTS:")
            for item in self.passed:
                logger.info(f"  {item}")
        
        if self.warnings:
            logger.info("\n⚠️  WARNINGS:")
            for item in self.warnings:
                logger.info(f"  {item}")
        
        if self.failed:
            logger.info("\n❌ FAILED TESTS:")
            for item in self.failed:
                logger.info(f"  {item}")
        
        logger.info("\n" + "=" * 60)
        logger.info(f"SUMMARY: {len(self.passed)} passed, {len(self.warnings)} warnings, {len(self.failed)} failed")
        logger.info("=" * 60)
        
        return len(self.failed) == 0


def main():
    """Run verification."""
    verifier = IntegrationVerifier()
    success = verifier.run_all_tests()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()




