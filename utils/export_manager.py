"""
Export Manager - Unified export functionality for all data types.

Supports:
- Campaign data export (CSV/JSON)
- Analytics data export
- Account data export
- Member data export
- Risk data export
"""

import logging
import json
import csv
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path
import sqlite3

logger = logging.getLogger(__name__)


class ExportManager:
    """Unified export manager for all data types."""
    
    def __init__(
        self,
        campaign_db_path: str = "campaigns.db",
        accounts_db_path: str = "accounts.db",
        members_db_path: str = "members.db",
        risk_db_path: str = "account_risk.db",
        audit_db_path: str = "accounts_audit.db"
    ):
        """Initialize export manager with database paths."""
        self.campaign_db_path = campaign_db_path
        self.accounts_db_path = accounts_db_path
        self.members_db_path = members_db_path
        self.risk_db_path = risk_db_path
        self.audit_db_path = audit_db_path
    
    # Campaign Exports
    
    def export_campaigns_to_csv(self, output_path: str, include_messages: bool = False) -> int:
        """
        Export campaigns to CSV.
        
        Args:
            output_path: Path to output CSV file
            include_messages: Whether to include individual messages
            
        Returns:
            Number of campaigns exported
        """
        try:
            with sqlite3.connect(self.campaign_db_path) as conn:
                conn.row_factory = sqlite3.Row
                
                # Get campaigns
                campaigns = conn.execute('SELECT * FROM campaigns ORDER BY created_at DESC').fetchall()
                
                if not campaigns:
                    return 0
                
                # Write campaigns CSV
                with open(output_path, 'w', newline='', encoding='utf-8') as f:
                    if campaigns:
                        writer = csv.DictWriter(f, fieldnames=campaigns[0].keys())
                        writer.writeheader()
                        for campaign in campaigns:
                            writer.writerow(dict(campaign))
                
                # Write messages CSV if requested
                if include_messages:
                    messages_path = output_path.replace('.csv', '_messages.csv')
                    messages = conn.execute('SELECT * FROM campaign_messages ORDER BY created_at DESC').fetchall()
                    
                    if messages:
                        with open(messages_path, 'w', newline='', encoding='utf-8') as f:
                            writer = csv.DictWriter(f, fieldnames=messages[0].keys())
                            writer.writeheader()
                            for message in messages:
                                writer.writerow(dict(message))
                
                logger.info(f"Exported {len(campaigns)} campaigns to {output_path}")
                return len(campaigns)
                
        except Exception as e:
            logger.error(f"Failed to export campaigns to CSV: {e}")
            raise
    
    def export_campaigns_to_json(self, output_path: str, include_messages: bool = False) -> int:
        """Export campaigns to JSON."""
        try:
            with sqlite3.connect(self.campaign_db_path) as conn:
                conn.row_factory = sqlite3.Row
                
                campaigns = conn.execute('SELECT * FROM campaigns ORDER BY created_at DESC').fetchall()
                
                if not campaigns:
                    return 0
                
                data = {
                    'exported_at': datetime.now().isoformat(),
                    'campaigns': [dict(c) for c in campaigns]
                }
                
                if include_messages:
                    messages = conn.execute('SELECT * FROM campaign_messages ORDER BY created_at DESC').fetchall()
                    data['messages'] = [dict(m) for m in messages]
                
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                
                logger.info(f"Exported {len(campaigns)} campaigns to {output_path}")
                return len(campaigns)
                
        except Exception as e:
            logger.error(f"Failed to export campaigns to JSON: {e}")
            raise
    
    # Analytics Exports
    
    def export_campaign_analytics_to_csv(self, campaign_id: int, output_path: str) -> bool:
        """Export campaign analytics to CSV."""
        try:
            with sqlite3.connect(self.campaign_db_path) as conn:
                conn.row_factory = sqlite3.Row
                
                # Get campaign info
                campaign = conn.execute('SELECT * FROM campaigns WHERE id = ?', (campaign_id,)).fetchone()
                if not campaign:
                    logger.warning(f"Campaign {campaign_id} not found")
                    return False
                
                # Get messages
                messages = conn.execute(
                    'SELECT * FROM campaign_messages WHERE campaign_id = ? ORDER BY created_at',
                    (campaign_id,)
                ).fetchall()
                
                if not messages:
                    logger.warning(f"No messages found for campaign {campaign_id}")
                    return False
                
                # Write to CSV
                with open(output_path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=messages[0].keys())
                    writer.writeheader()
                    for message in messages:
                        writer.writerow(dict(message))
                
                logger.info(f"Exported analytics for campaign {campaign_id} to {output_path}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to export campaign analytics: {e}")
            raise
    
    def export_delivery_analytics_to_csv(self, output_path: str, days: int = 7) -> bool:
        """Export delivery analytics to CSV."""
        try:
            # Check if delivery analytics DB exists
            delivery_db = "delivery_analytics.db"
            if not Path(delivery_db).exists():
                logger.warning(f"Delivery analytics DB not found: {delivery_db}")
                return False
            
            with sqlite3.connect(delivery_db) as conn:
                conn.row_factory = sqlite3.Row
                
                # Get recent delivery events
                cutoff = datetime.now().timestamp() - (days * 86400)
                events = conn.execute(
                    'SELECT * FROM delivery_events WHERE timestamp >= ? ORDER BY timestamp DESC',
                    (cutoff,)
                ).fetchall()
                
                if not events:
                    logger.warning("No delivery events found")
                    return False
                
                # Write to CSV
                with open(output_path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=events[0].keys())
                    writer.writeheader()
                    for event in events:
                        writer.writerow(dict(event))
                
                logger.info(f"Exported {len(events)} delivery events to {output_path}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to export delivery analytics: {e}")
            raise
    
    # Account Exports
    
    def export_accounts_to_csv(self, output_path: str) -> int:
        """Export accounts to CSV."""
        try:
            with sqlite3.connect(self.accounts_db_path) as conn:
                conn.row_factory = sqlite3.Row
                
                accounts = conn.execute('SELECT * FROM accounts ORDER BY created_at DESC').fetchall()
                
                if not accounts:
                    return 0
                
                # Parse account_data JSON for export
                export_data = []
                for account in accounts:
                    row = dict(account)
                    if 'account_data' in row:
                        try:
                            account_data = json.loads(row['account_data'])
                            row.update(account_data)
                        except:
                            pass
                    export_data.append(row)
                
                # Write to CSV
                if export_data:
                    with open(output_path, 'w', newline='', encoding='utf-8') as f:
                        writer = csv.DictWriter(f, fieldnames=export_data[0].keys())
                        writer.writeheader()
                        for row in export_data:
                            writer.writerow(row)
                
                logger.info(f"Exported {len(accounts)} accounts to {output_path}")
                return len(accounts)
                
        except Exception as e:
            logger.error(f"Failed to export accounts: {e}")
            raise
    
    # Risk Exports
    
    def export_risk_data_to_csv(self, output_path: str) -> int:
        """Export account risk data to CSV."""
        try:
            with sqlite3.connect(self.risk_db_path) as conn:
                conn.row_factory = sqlite3.Row
                
                risk_scores = conn.execute(
                    'SELECT * FROM account_risk_scores ORDER BY overall_score DESC'
                ).fetchall()
                
                if not risk_scores:
                    return 0
                
                with open(output_path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=risk_scores[0].keys())
                    writer.writeheader()
                    for score in risk_scores:
                        writer.writerow(dict(score))
                
                logger.info(f"Exported {len(risk_scores)} risk scores to {output_path}")
                return len(risk_scores)
                
        except Exception as e:
            logger.error(f"Failed to export risk data: {e}")
            raise
    
    # Member Exports
    
    def export_members_to_csv(self, output_path: str, channel_id: Optional[int] = None) -> int:
        """Export members to CSV."""
        try:
            with sqlite3.connect(self.members_db_path) as conn:
                conn.row_factory = sqlite3.Row
                
                if channel_id:
                    members = conn.execute(
                        'SELECT * FROM members WHERE channel_id = ? ORDER BY first_seen DESC',
                        (channel_id,)
                    ).fetchall()
                else:
                    members = conn.execute('SELECT * FROM members ORDER BY first_seen DESC').fetchall()
                
                if not members:
                    return 0
                
                with open(output_path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=members[0].keys())
                    writer.writeheader()
                    for member in members:
                        writer.writerow(dict(member))
                
                logger.info(f"Exported {len(members)} members to {output_path}")
                return len(members)
                
        except Exception as e:
            logger.error(f"Failed to export members: {e}")
            raise
    
    # Cost/Audit Exports
    
    def export_cost_data_to_csv(self, output_path: str, days: Optional[int] = None) -> int:
        """Export cost/audit data to CSV."""
        try:
            with sqlite3.connect(self.audit_db_path) as conn:
                conn.row_factory = sqlite3.Row
                
                if days:
                    cutoff = datetime.now().timestamp() - (days * 86400)
                    events = conn.execute(
                        'SELECT * FROM audit_events WHERE timestamp >= ? ORDER BY timestamp DESC',
                        (cutoff,)
                    ).fetchall()
                else:
                    events = conn.execute('SELECT * FROM audit_events ORDER BY timestamp DESC').fetchall()
                
                if not events:
                    return 0
                
                with open(output_path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=events[0].keys())
                    writer.writeheader()
                    for event in events:
                        writer.writerow(dict(event))
                
                logger.info(f"Exported {len(events)} audit events to {output_path}")
                return len(events)
                
        except Exception as e:
            logger.error(f"Failed to export cost data: {e}")
            raise


# Singleton
_export_manager: Optional[ExportManager] = None


def get_export_manager(**kwargs) -> ExportManager:
    """Get singleton export manager."""
    global _export_manager
    if _export_manager is None:
        _export_manager = ExportManager(**kwargs)
    return _export_manager






